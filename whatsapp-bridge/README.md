# BloodBeacon WhatsApp Bridge

Baileys-based WhatsApp automation bridge for blood donor activation. **Demo/spare number use only.**

## Setup

### Prerequisites

- Node.js >= 20
- A spare WhatsApp account (demo number — not your personal account)
- `.env` with `BRIDGE_SECRET` and `FLASK_URL` (see below)

### Install & Run

```bash
npm install
FLASK_URL=http://localhost:5001 BRIDGE_SECRET=your-secret node index.js
```

### QR Login

On first run, a QR code will be displayed in the terminal. Scan it with WhatsApp on the spare phone:

1. Open WhatsApp on the spare phone
2. Go to **Settings > Linked devices**
3. Tap **Link a device**
4. Scan the QR code from the terminal

The bridge will automatically detect the connection and start listening for donor replies.

## Environment Variables

- `FLASK_URL` — Flask app URL (default: `http://localhost:5001`)
- `BRIDGE_SECRET` — Required shared secret with Flask; set it in the environment
  or `whatsapp-bridge/.env`. The bridge refuses to start if it is unset.
- `BRIDGE_PORT` — HTTP API port (default: `3100`)

## API Contract with Flask

### Bridge → Flask

**POST `/internal/whatsapp-reply`**
- Headers: `X-Bridge-Secret: <secret>`
- Body: `{ phone, text, message_id }`
- Used by: Bridge to report incoming donor replies

**GET `/internal/ping`**
- Headers: `X-Bridge-Secret: <secret>`
- Used by the bridge at startup to verify Flask authentication

### Flask → Bridge

**GET `/status`**
- Headers: `X-Bridge-Secret: <secret>`
- Response: `{ connected: boolean }`
- Used by: Staff dashboard to show bridge connection status

**POST `/send`**
- Headers: `X-Bridge-Secret: <secret>`
- Body: `{ phone, message }`
- Response: `{ ok: true }` or error
- Used by: Flask to send Wave 1 alerts

## Reliability Features

1. **Message Deduplication:** Each message ID is processed exactly once. Upserts with type `notify` or `append` are both handled.

2. **Auto-Reconnect:** The bridge automatically reconnects on transient failures. It does NOT reconnect after a `loggedOut` status (requires manual QR re-scan).

3. **Single Instance:** Only one bridge should run at a time (enforced by process management; lock file support planned).

4. **Flask Timeout:** All Flask calls have a 30-second timeout to prevent hanging.

5. **Per-Chat Isolation:** Failure in one chat never blocks others.

## Testing

```bash
npm test
```

Runs unit tests for message deduplication and reconnect logic (no real WhatsApp contact).

## Troubleshooting

**Bridge stuck after disconnect:**
- Check Flask is running: `curl http://localhost:5001/health`
- Restart the bridge with `node index.js` (it will request a new QR)

**Bridge reports `Flask auth FAILED`:**
- Confirm Flask and the bridge use the same non-empty `BRIDGE_SECRET`.
- The bridge logs each inbound raw JID and resolved phone; `@lid` messages
  use Baileys alternate phone identities when available.

**Message delays:**
- WhatsApp may rate-limit replies; typically <5s per donor
- Check network connectivity

**Bridge keeps reconnecting:**
- Verify `FLASK_URL` is correct
- Check `.env` for typos in `BRIDGE_SECRET`

## License

Part of BloodBeacon — see main repo LICENSE.
