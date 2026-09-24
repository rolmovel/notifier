/**
 * WhatsApp Bridge — Baileys HTTP server for the desktop utility.
 *
 * Endpoints:
 *   GET   /status      — check connection state
 *   GET   /qr          — get current QR code string
 *   POST  /connect     — (re)start Baileys pairing
 *   POST  /pair        — request pairing code (phone number)
 *   POST  /logout      — close session and clear auth state
 *   POST  /send        — send a text message (returns accepted + message_id)
 *   GET   /message/:id — query the real delivery status of a message
 *
 * Auth state is persisted to a user-writable directory:
 *   - $WHATSAPP_AUTH_DIR if set (passed by the Python host)
 *   - otherwise %APPDATA%\whatsapp-notifier\bridge-auth (Windows)
 *             or ~/.config/whatsapp-notifier/bridge-auth (POSIX)
 * This is required because Program Files is read-only for non-admin users.
 */

import express from 'express';
import {
    default as makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
    Browsers,
} from '@whiskeysockets/baileys';
import { Boom } from '@hapi/boom';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import pino from 'pino';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

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

// Numeric values of proto.WebMessageInfo.Status as emitted by Baileys 6.x
// in the 'messages.update' event (NOT strings).
const MSG_STATUS = {
    ERROR: 0,
    PENDING: 1,
    SERVER_ACK: 2,
    DELIVERY_ACK: 3,
    READ: 4,
    PLAYED: 5,
};

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

// Temporary, payload-free diagnostics for the delivery investigation.
// One JSON object per line; never logs message text.
const diagnosticLogPath = path.join(authDir, 'receipt-diagnostics.jsonl');
function diagnosticLog(event, data = {}) {
    try {
        fs.appendFileSync(
            diagnosticLogPath,
            JSON.stringify({
                timestamp: new Date().toISOString(),
                event,
                ...data,
            }) + '\\n',
            'utf8',
        );
    } catch (err) {
        console.error('Diagnostic log failed:', err.message);
    }
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
    receiptMap.clear();
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
            logger: pino({ level: 'warn' }),
        });

        sock.ev.on('creds.update', saveCreds);

        // Track delivery receipts so clients can query the real status of a message.
        sock.ev.on('messages.update', (updates) => {
            diagnosticLog('messages.update.batch', {
                count: Array.isArray(updates) ? updates.length : 0,
                items: (updates || []).map(({ key, update, status }) => ({
                    id: key?.id || null,
                    remoteJid: key?.remoteJid || null,
                    fromMe: key?.fromMe ?? null,
                    updateKeys: update ? Object.keys(update) : [],
                    statusRaw: update?.status ?? status ?? null,
                    statusType: typeof (update?.status ?? status),
                })),
            });
            for (const { key, update, status } of updates || []) {
                if (!key || !key.id) continue;
                const entry = ensureReceipt(key.id);
                // Baileys 6.x emits WAMessageUpdate as { key, update: { status } }.
                // Keep the top-level fallback for compatibility with older versions.
                const s = Number(update?.status ?? status);
                if (s === MSG_STATUS.SERVER_ACK) entry.server_ack = true;
                if (s === MSG_STATUS.DELIVERY_ACK
                    || s === MSG_STATUS.READ
                    || s === MSG_STATUS.PLAYED) {
                    entry.delivery_ack = true;
                }
                if (s === MSG_STATUS.ERROR) entry.status = 'ERROR';
                entry.updated_at = Math.floor(Date.now() / 1000);
                diagnosticLog('messages.update.item', {
                    id: key.id,
                    statusRaw: update?.status ?? status ?? null,
                    statusNumber: s,
                    aggregate: toAggregateStatus(entry),
                    serverAck: entry.server_ack,
                    deliveryAck: entry.delivery_ack,
                });
            }
        });

        // Some Baileys flows expose delivery/read acknowledgements through
        // message-receipt.update instead of messages.update.
        sock.ev.on('message-receipt.update', (updates) => {
            diagnosticLog('message-receipt.update.batch', {
                count: Array.isArray(updates) ? updates.length : 0,
                items: (updates || []).map(({ key, receipt }) => ({
                    id: key?.id || null,
                    remoteJid: key?.remoteJid || null,
                    fromMe: key?.fromMe ?? null,
                    receiptKeys: receipt ? Object.keys(receipt) : [],
                    hasReceiptTimestamp: Boolean(receipt?.receiptTimestamp),
                    hasReadTimestamp: Boolean(receipt?.readTimestamp),
                    hasPlayedTimestamp: Boolean(receipt?.playedTimestamp),
                })),
            });
            for (const { key, receipt } of updates || []) {
                if (!key || !key.id) continue;
                const entry = ensureReceipt(key.id);
                if (receipt?.receiptTimestamp || receipt?.readTimestamp || receipt?.playedTimestamp) {
                    entry.delivery_ack = true;
                    entry.updated_at = Math.floor(Date.now() / 1000);
                }
            }
        });

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

// POST /send — accept a text message for sending (returns accepted + message_id)
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
        diagnosticLog('send.accepted', {
            messageId,
            remoteJid: sent.key.remoteJid || null,
            fromMe: sent.key.fromMe ?? null,
            timestamp: sent.messageTimestamp || Math.floor(Date.now() / 1000),
        });

        res.json({
            accepted: true,
            success: true, // deprecated alias kept for older clients
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
    const response = {
        message_id: messageId,
        status: toAggregateStatus(entry),
        server_ack: entry.server_ack,
        delivery_ack: entry.delivery_ack,
        updated_at: entry.updated_at,
    };
    diagnosticLog('message.status.response', response);
    res.json(response);
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