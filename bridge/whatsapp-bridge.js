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
// Whether to auto-reconnect after a connection drop. Set to false on logout
// so the bridge stays disconnected until the user explicitly reconnects.
let shouldReconnect = true;

// Receipt map: message_id -> { status, server_ack, delivery_ack, updated_at }
// Fed by the 'messages.update' event. Volatile (in-memory only).
const receiptMap = new Map();

function ensureReceipt(messageId) {
    if (!receiptMap.has(messageId)) {
        receiptMap.set(messageId, {
            status: 'sending',
            server_ack: false,
            delivery_ack: false,
            updated_at: Math.floor(Date.now() / 1000),
        });
    }
    return receiptMap.get(messageId);
}

function toAggregateStatus(entry) {
    if (entry.delivery_ack) return 'delivered';
    if (entry.server_ack) return 'pending';
    if (entry.status === 'ERROR') return 'failed';
    return 'sending';
}

const authDir = path.join(__dirname, 'auth');
if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir, { recursive: true });
}

// Clear the persisted auth state and connection state (used on logout).
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
    receiptMap.clear();
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

    // Track delivery receipts so clients can query the real status of a message.
    sock.ev.on('messages.update', (updates) => {
        for (const { key, status } of updates || []) {
            if (!key || !key.id) continue;
            const entry = ensureReceipt(key.id);
            const statusStr = String(status || '');
            if (statusStr === 'SERVER_ACK') entry.server_ack = true;
            if (statusStr === 'DELIVERY_ACK' || statusStr === 'READ') {
                entry.delivery_ack = true;
            }
            if (statusStr === 'ERROR') entry.status = 'ERROR';
            entry.updated_at = Math.floor(Date.now() / 1000);
        }
    });

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
                clearAuth();
                if (shouldReconnect) {
                    startBaileys();
                }
            } else {
                connectionState = 'close';
                if (shouldReconnect) {
                    // Reconnect
                    console.log('Reconnecting...');
                    startBaileys();
                } else {
                    console.log('Disconnected — waiting for explicit reconnect');
                }
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

// POST /connect — (re)start Baileys pairing (used from the Settings dialog)
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

// POST /logout — close the session and clear auth so a new number can be linked
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

        const messageId = sent.key.id;
        ensureReceipt(messageId);

        res.json({
            accepted: true,
            message_id: messageId,
            status: 'sending',
            timestamp: sent.messageTimestamp || Math.floor(Date.now() / 1000),
        });
    } catch (err) {
        console.error('Send error:', err.message);
        res.status(500).json({ error: err.message || 'Failed to send message' });
    }
});

// GET /message/:id — query the real delivery status of a sent message
app.get('/message/:id', (req, res) => {
    const messageId = req.params.id;
    if (connectionState !== 'open') {
        return res.status(409).json({ error: 'Not connected to WhatsApp' });
    }
    const entry = receiptMap.get(messageId);
    if (!entry) {
        return res.status(404).json({ error: 'Unknown message id' });
    }
    res.json({
        message_id: messageId,
        status: toAggregateStatus(entry),
        server_ack: entry.server_ack,
        delivery_ack: entry.delivery_ack,
        updated_at: entry.updated_at,
    });
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
