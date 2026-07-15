/**
 * WhatsApp Bridge — Baileys HTTP server for the desktop utility.
 *
 * Endpoints:
 *   GET  /status  — check connection state
 *   GET  /qr      — get current QR code string
 *   POST /pair    — request pairing code (phone number)
 *   POST /send    — send a text message
 *
 * Auth state is persisted to ./auth/ (relative to bridge/ directory).
 */

const express = require('express');
const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
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
let connectionState = 'connecting';
let currentQR = null;
let connectionPhone = null;

const authDir = path.join(__dirname, 'auth');
if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir, { recursive: true });
}

async function startBaileys() {
    const { version, isLatest } = await fetchLatestBaileysVersion();
    console.log(`Baileys version: ${version} (latest: ${isLatest})`);

    const { state, saveCreds } = await useMultiFileAuthState(authDir);

    sock = makeWASocket({
        version,
        auth: state,
        printQRInTerminal: false,
        logger: require('pino')({ level: 'warn' }),
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            currentQR = qr;
            connectionState = 'close';
            console.log('QR code generated, waiting for scan');
        }

        if (connection === 'connecting') {
            connectionState = 'connecting';
            console.log('Connecting to WhatsApp...');
        }

        if (connection === 'open') {
            connectionState = 'open';
            currentQR = null;
            console.log('WhatsApp connected!');
        }

        if (connection === 'close') {
            const statusCode = new Boom(lastDisconnect?.error)?.output?.statusCode;
            console.log(`Connection closed. Status: ${statusCode}`);

            if (statusCode === DisconnectReason.loggedOut) {
                // Session was logged out — clear auth state
                console.log('Logged out. Clearing auth state.');
                fs.rmSync(authDir, { recursive: true, force: true });
                fs.mkdirSync(authDir, { recursive: true });
                connectionState = 'close';
                startBaileys();
            } else {
                connectionState = 'close';
                // Reconnect
                console.log('Reconnecting...');
                startBaileys();
            }
        }
    });
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
        // Request pairing code
        const pairingCode = await sock.requestPairingCode(phone.replace('+', ''));
        connectionPhone = phone;
        res.json({
            pairing_code: pairingCode,
            expires_in: 90,
        });
    } catch (err) {
        console.error('Pairing error:', err.message);
        res.status(500).json({ error: 'Failed to request pairing code' });
    }
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
    startBaileys().catch((err) => {
        console.error('Failed to start Baileys:', err);
        connectionState = 'close';
    });
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
