// BloodBeacon message handler and bridge API
// Processes incoming WhatsApp replies and routes to Flask

export function digitsOnlyPhone(phone) {
  return String(phone || '').replace(/\D/g, '');
}

export function createMessageHandler({
  socket, flask, logger, seen, stateStore, bridgeSecret, fetchImpl = fetch,
}) {
  if (!bridgeSecret) throw new Error('bridgeSecret is required');

  async function post(url, body) {
    console.log(`Posting to Flask: ${url}`);
    const response = await fetchImpl(`${flask}${url}`, {
      method: 'POST',
      body: JSON.stringify(body),
      headers: { 'Content-Type': 'application/json', 'X-Bridge-Secret': bridgeSecret },
      signal: AbortSignal.timeout(30 * 1000), // 30s timeout per spec
    });
    console.log(`Flask response: ${response.status}`);
    if (!response.ok) {
      throw new Error(`${url} HTTP ${response.status}`);
    }
    return response.json().catch(() => ({}));
  }

  return async (message) => {
    const messageId = message.key.id;
    if (!messageId) return;

    // Dedupe: process each message ID exactly once
    if (stateStore.isProcessed(messageId)) {
      console.log(`Message ${messageId} already processed, skipping`);
      return;
    }
    stateStore.markProcessed(messageId);
    await stateStore.save();

    // Only process text messages from individual chats (not groups)
    if (!message.message?.conversation && !message.message?.extendedTextMessage?.text) return;
    if (message.key.fromMe) return; // Ignore our own messages
    if (message.key.remoteJid?.includes('@g.us')) return; // Ignore group messages

    const text = (message.message?.conversation || message.message?.extendedTextMessage?.text || '').trim();
    const rawJid = message.key.remoteJid || '';
    const alternateIdentity = message.key.remoteJidAlt
      || message.key.participantAlt
      || message.key.senderPn;
    const resolvedPhone = rawJid.endsWith('@lid')
      ? digitsOnlyPhone(alternateIdentity)
      : digitsOnlyPhone(rawJid.replace('@s.whatsapp.net', ''));
    const sender = resolvedPhone || rawJid;

    console.log(`Inbound message: raw JID=${rawJid}, resolved phone=${sender}, text="${text}"`);
    if (!text) return;

    try {
      await post('/internal/whatsapp-reply', {
        phone: sender,
        text,
        message_id: messageId,
      });
      console.log(`Reply from ${sender} posted to Flask`);
    } catch (error) {
      logger.error('Failed to post reply to Flask:', error?.stack || error);
    }
  };
}

// HTTP API server for Flask -> Bridge communication
export async function createBridgeAPI({ socket, bridgeSecret = '', port = 3100 }) {
  const { createServer } = await import('node:http');

  const server = createServer(async (req, res) => {
    // Check secret on all requests
    const secret = req.headers['x-bridge-secret'];
    if (!bridgeSecret || secret !== bridgeSecret) {
      res.writeHead(401, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Unauthorized' }));
      return;
    }

    if (req.method === 'GET' && req.url === '/status') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ connected: !!socket }));
      return;
    }

    if (req.method === 'POST' && req.url === '/send') {
      let body = '';
      req.on('data', (chunk) => { body += chunk; });
      req.on('end', async () => {
        try {
          const { phone, message } = JSON.parse(body);
          const normalizedPhone = digitsOnlyPhone(phone);
          if (!normalizedPhone || !message) {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Missing phone or message' }));
            return;
          }

          // Send message via Baileys
          if (socket) {
            const jid = `${normalizedPhone}@s.whatsapp.net`;
            await socket.sendMessage(jid, { text: message });
            console.log(`Sent to ${normalizedPhone}: "${message}"`);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ ok: true }));
          } else {
            res.writeHead(503, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Bridge not connected' }));
          }
        } catch (error) {
          console.error('Send failed:', error);
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: error.message }));
        }
      });
      return;
    }

    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not found' }));
  });

  server.listen(port, '127.0.0.1', () => {
    console.log(`Bridge API listening on http://127.0.0.1:${port}`);
  });

  return server;
}
