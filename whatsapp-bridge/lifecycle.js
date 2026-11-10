export function createBridgeLifecycle({
  makeSocket, createHandler, saveCreds, loggedOutStatus, checkFlask, showQr,
  log = console, schedule = setTimeout, reconnectDelay = 5000,
}) {
  let active;
  let reconnectScheduled = false;
  const queues = new Map();

  function retry() {
    if (reconnectScheduled) return;
    reconnectScheduled = true;
    log.log(`Reconnecting in ${reconnectDelay / 1000} seconds`);
    schedule(() => {
      reconnectScheduled = false;
      try {
        connect();
      } catch (error) {
        log.error('Reconnect failed:', error?.stack || error);
        retry();
      }
    }, reconnectDelay);
  }

  function connect() {
    const socket = makeSocket();
    active = socket;
    const handle = createHandler(socket, queues);

    socket.ev.on('creds.update', () => {
      saveCreds().catch((error) => log.error('Saving credentials failed:', error?.stack || error));
    });

    socket.ev.on('messages.upsert', ({ type, messages }) => {
      // Handle both 'notify' (new messages) and 'append' (message history/restored)
      if (type !== 'notify' && type !== 'append') return;
      for (const message of messages) {
        handle(message).catch((error) => log.error('Message handler failed:', error?.stack || error));
      }
    });

    socket.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
      if (qr && active === socket) showQr(qr);

      if (connection === 'open') {
        log.log(`[${new Date().toISOString()}] WhatsApp connection open`);
        if (active !== socket) return;
        log.log('BloodBeacon WhatsApp bridge is listening');
        checkFlask().catch((error) => log.error('Flask unreachable:', error?.stack || error));
      }

      if (connection === 'close') {
        const error = lastDisconnect?.error;
        const status = error?.output?.statusCode;
        log.error(`[${new Date().toISOString()}] WhatsApp connection closed (status ${status ?? 'unknown'}):`,
          error?.stack || error?.message || String(error ?? 'reason unavailable'));
        if (active !== socket) return;
        active = undefined;

        // Do not reconnect if logged out; require fresh QR scan
        if (status === loggedOutStatus) {
          log.error('WHATSAPP LOGGED OUT: A fresh QR scan is required. Restart the bridge to relink the demo number.');
          return;
        }

        // Auto-reconnect on transient failures
        retry();
      }
    });
  }

  return { connect, getActive: () => active };
}
