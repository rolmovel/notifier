/**
 * WhatsApp Bridge — Baileys HTTP server for the desktop utility.
 *
 * Endpoints:
 *   GET  /status  — check connection state
 *   GET  /qr      — get current QR code string
 *   POST /pair    — request pairing code (phone number)
 *   POST /send    — send a text message
 *
 * Auth state is persisted to a user-writable directory:
 *   - $WHATSAPP_AUTH_DIR if set (passed by the Python host)
 *   - otherwise %APPDATA%\whatsapp-notifier\bridge-auth (Windows)
 *             or ~/.config/whatsapp-notifier/bridge-auth (POSIX)
 * This is required because Program Files is read-only for non-admin users.
 */

const express = require('express');
const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
    Browsers,
} = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const path = require('path');
const fs = require('fs');

// Parse CLI args
const args = process.argv.slice(2);
let port = 3001;
for (let i = 0; i < args.length; i++) {
    if (args[i] === '--port' && args[i + 1]) {
        port = parseInt(args[i + 1], 10);
    }
}

const app = express();
app.use(express.json({ limit: '10mb' }));

// Global state
let sock = null;
let connectionState = 'close';
let currentQR = null;
let connectionPhone = null;
let isStarting = false;
let shouldReconnect = false;

function resolveAuthDir() {
    if (process.env.WHATSAPP_AUTH_DIR) {
        return process.env.WHATSAPP_AUTH_DIR;
    }
    const appName = 'whatsapp-notifier';
    const subdir = 'bridge-auth';
    if (process.platform === 'win32' && process.env.APPDATA) {
        return path.join(process.env.APPDATA, appName, subdir);
    }
    if (process.platform === 'darwin' && process.env.HOME) {
        return path.join(process.env.HOME, 'Library', 'Application Support', appName, subdir);
    }
    const xdg = process.env.XDG_CONFIG_HOME || (process.env.HOME && path.join(process.env.HOME, '.config'));
    if (xdg) {
        return path.join(xdg, appName, subdir);
    }
    // Fallback: relative to bridge dir (dev mode only)
    return path.join(__dirname, 'auth');
}

const authDir = resolveAuthDir();
if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir, { recursive: true });
}

function clearAuth() {
    try {
        fs.rmSync(authDir, { recursive: true, force: true });
        fs.mkdirSync(authDir, { recursive: true });
    } catch (err) {
        console.error('Failed to clear auth:', err.message);
    }
    connectionState = 'close';
    currentQR = null;
    connectionPhone = null;
    shouldReconnect = false;
}

function handleConnectionUpdate(update) {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
        currentQR = qr;
        connectionState = 'connecting';
        console.log('QR code generated, waiting for scan');
    }

    if (connection === 'connecting') {
        connectionState = 'connecting';
        console.log('Connecting to WhatsApp...');
    }

    if (connection === 'open') {
        connectionState = 'open';
        currentQR = null;
        shouldReconnect = true;
        console.log('WhatsApp connected!');
    }

    if (connection === 'close') {
        const statusCode = new Boom(lastDisconnect?.error)?.output?.statusCode;
        console.log(`Connection closed. Status: ${statusCode}`);
        connectionState = 'close';
        currentQR = null;

        if (statusCode === DisconnectReason.loggedOut) {
            console.log('Logged out. Clearing auth state.');
            clearAuth();
        } else if (shouldReconnect) {
            // restartRequired (515) is a normal part of the QR pairing flow:
            // WhatsApp asks the client to restart with the new credentials.
            const delay = statusCode === DisconnectReason.restartRequired ? 0 : 3000;
            console.log(`Reconnecting in ${delay}ms (status ${statusCode})...`);
            setTimeout(() => startBaileys(), delay);
        }
    }
}

async function startBaileys() {
    if (isStarting) {
        console.log('startBaileys already in progress, skipping');
        return;
    }
    isStarting = true;
    try {
        // Close any existing socket to avoid duplicate connections
        if (sock) {
            try {
                sock.end();
            } catch (err) {
                console.error('Error ending previous socket:', err.message);
            }
            sock = null;
        }

        const { version, isLatest } = await fetchLatestBaileysVersion();
        console.log(`Baileys version: ${version} (latest: ${isLatest})`);

        const { state, saveCreds } = await useMultiFileAuthState(authDir);

        sock = makeWASocket({
            version,
            auth: state,
            browser: Browsers.ubuntu('Chrome'),
            printQRInTerminal: false,
            markOnlineOnConnect: false,
            qrTimeout: 120000,
            syncFullHistory: false,
            logger: require('pino')({ level: 'warn' }),
        });

        sock.ev.on('creds.update', saveCreds);
        sock.ev.on('connection.update', handleConnectionUpdate);
    } catch (err) {
        console.error('Failed to start Baileys:', err);
        connectionState = 'close';
    } finally {
        isStarting = false;
    }
}

// --- Endpoints ---

// GET /status — check connection state
app.get('/status', (req, res) => {
    res.json({
        connected: connectionState === 'open',
        state: connectionState,
        phone: connectionPhone || null,
    });
});

// GET /qr — get current QR code string
app.get('/qr', (req, res) => {
    if (connectionState === 'open') {
        return res.status(409).json({ error: 'Already connected' });
    }
    if (!currentQR) {
        return res.status(503).json({ error: 'QR not yet available' });
    }
    res.json({
        qr_code: currentQR,
        expires_in: 60,
    });
});

// POST /connect — explicitly start Baileys and begin pairing
app.post('/connect', (req, res) => {
    if (connectionState === 'open') {
        return res.status(409).json({ error: 'Already connected' });
    }
    if (connectionState === 'connecting') {
        return res.json({ success: true, state: 'connecting' });
    }
    connectionState = 'connecting';
    shouldReconnect = true;
    startBaileys().catch((err) => {
        console.error('Failed to start Baileys:', err);
        connectionState = 'close';
    });
    res.json({ success: true, state: 'connecting' });
});

// POST /pair — request pairing code (alternative to QR)
app.post('/pair', async (req, res) => {
    const { phone } = req.body;
    if (!phone) {
        return res.status(400).json({ error: 'Phone number is required' });
    }
    if (connectionState === 'open') {
        return res.status(409).json({ error: 'Already connected' });
    }
    try {
        if (!sock) {
            return res.status(503).json({ error: 'WhatsApp socket not ready. Try again in a few seconds.' });
        }
        const pairingCode = await sock.requestPairingCode(phone.replace(/\+/g, '').replace(/\s/g, ''));
        connectionPhone = phone;
        res.json({
            pairing_code: pairingCode,
            expires_in: 90,
        });
    } catch (err) {
        console.error('Pairing error:', err.message, err.stack);
        res.status(500).json({ error: err.message || 'Failed to request pairing code' });
    }
});

// POST /logout — disconnect and clear auth state so a new number can be linked
app.post('/logout', (req, res) => {
    shouldReconnect = false;
    if (sock) {
        try {
            sock.end();
        } catch (err) {
            console.error('Error ending socket:', err.message);
        }
        sock = null;
    }
    clearAuth();
    console.log('Logged out, auth state cleared. Ready for new pairing.');
    res.json({ success: true, message: 'Logged out, ready for new pairing' });
});

// POST /send — send a text message
app.post('/send', async (req, res) => {
    const { number, text } = req.body;

    if (!number || !text) {
        return res.status(400).json({ error: 'Number and text are required' });
    }

    if (connectionState !== 'open') {
        return res.status(409).json({ error: 'Not connected to WhatsApp' });
    }

    try {
        // Format JID: number@s.whatsapp.net
        const jid = number.replace('+', '').replace(/\s/g, '') + '@s.whatsapp.net';

        const sent = await sock.sendMessage(jid, { text: text });

        res.json({
            success: true,
            message_id: sent.key.id,
            timestamp: sent.messageTimestamp || Math.floor(Date.now() / 1000),
        });
    } catch (err) {
        console.error('Send error:', err.message);
        res.status(500).json({ error: err.message || 'Failed to send message' });
    }
});

// Start server
app.listen(port, '127.0.0.1', () => {
    console.log(`WhatsApp bridge listening on http://127.0.0.1:${port}`);
    // Do NOT auto-start Baileys. Wait for an explicit POST /connect request.
});

// Graceful shutdown
process.on('SIGTERM', () => {
    console.log('SIGTERM received, shutting down...');
    if (sock) {
        sock.end();
    }
    process.exit(0);
});

process.on('SIGINT', () => {
    console.log('SIGINT received, shutting down...');
    if (sock) {
        sock.end();
    }
    process.exit(0);
});
