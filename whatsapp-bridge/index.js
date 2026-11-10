// Unofficial WhatsApp automation: use a spare/demo number only.
// BloodBeacon Baileys bridge for blood donor activation via WhatsApp.
import path from 'node:path';
import { chmod, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import makeWASocket, {
  DisconnectReason, useMultiFileAuthState,
} from '@whiskeysockets/baileys';
import pino from 'pino';
import qrcode from 'qrcode-terminal';
import { createMessageHandler, createBridgeAPI } from './messages.js';
import { createStateStore } from './state.js';
import { createBridgeLifecycle } from './lifecycle.js';

const root = path.dirname(fileURLToPath(import.meta.url));
const flask = process.env.FLASK_URL || 'http://localhost:5001';
const logger = pino({ level: 'warn' });
const stateStore = createStateStore(path.join(root, 'bridge-state.json'));
const authDir = path.join(root, '.baileys_auth');
const bridgeSecret = process.env.BRIDGE_SECRET || 'dev-secret-no-prod-use';

await stateStore.load();
await mkdir(authDir, { recursive: true, mode: 0o700 });
await chmod(authDir, 0o700);

const { state, saveCreds } = await useMultiFileAuthState(authDir);

// Start the bridge with lifecycle management
const bridge = createBridgeLifecycle({
  makeSocket: () => makeWASocket({ auth: state, logger }),
  createHandler: (socket) => createMessageHandler({
    socket, flask, logger, stateStore,
  }),
  saveCreds: async () => {
    await saveCreds();
  },
  loggedOutStatus: DisconnectReason.loggedOut,
  checkFlask: async () => {
    const response = await fetch(`${flask}/health`, { signal: AbortSignal.timeout(5000) });
    if (!response.ok) throw new Error(`Flask health check HTTP ${response.status}`);
  },
  showQr: (qr) => {
    console.log('Scan the QR with a demo/spare number: WhatsApp > Settings > Linked Devices > Link a device');
    qrcode.generate(qr, { small: true });
  },
});

console.log(`Starting BloodBeacon Baileys bridge. Flask target: ${flask}`);
bridge.connect();

// Start the HTTP API server for Flask communication
const active = bridge.getActive?.();
await createBridgeAPI({
  socket: active,
  bridgeSecret,
  port: parseInt(process.env.BRIDGE_PORT || '3100', 10),
});

console.log('BloodBeacon bridge ready');
