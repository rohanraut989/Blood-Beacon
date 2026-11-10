import test from 'node:test';
import assert from 'node:assert';
import { createStateStore } from '../state.js';
import { createBridgeLifecycle } from '../lifecycle.js';
import { createBridgeAPI, createMessageHandler, digitsOnlyPhone } from '../messages.js';
import { requireBridgeSecret } from '../config.js';
import { spawnSync } from 'node:child_process';
import { unlink } from 'node:fs/promises';

test('Phone normalization: bridge JID input is digits-only', () => {
  assert.strictEqual(digitsOnlyPhone('+91 98765-43210'), '919876543210');
  assert.strictEqual(digitsOnlyPhone('977-9817612738'), '9779817612738');
});

test('Inbound @lid message forwards its alternate digits-only phone', async () => {
  const statePath = `lid-test-${process.pid}-${Date.now()}`;
  const store = createStateStore(statePath);
  await store.load();
  const requests = [];
  const handler = createMessageHandler({
    socket: {},
    flask: 'http://flask',
    logger: console,
    stateStore: store,
    bridgeSecret: 'shared-secret',
    fetchImpl: async (url, options) => {
      requests.push({ url, options });
      return { status: 200, ok: true, json: async () => ({ ok: true }) };
    },
  });

  await handler({
    key: {
      id: 'lid-message-1',
      remoteJid: '1234567890@lid',
      remoteJidAlt: '+91 98765-43210@s.whatsapp.net',
    },
    message: { conversation: '2' },
  });

  assert.strictEqual(requests.length, 1);
  assert.strictEqual(JSON.parse(requests[0].options.body).phone, '919876543210');
  assert.strictEqual(requests[0].options.headers['X-Bridge-Secret'], 'shared-secret');
  await unlink(statePath);
});

test('Inbound @lid message resolves through the persisted LID map', async () => {
  const statePath = `lid-map-test-${process.pid}-${Date.now()}`;
  const saved = createStateStore(statePath);
  saved.setLidPhone('103860949528819@lid', '+91 98765-43210');
  await saved.save();

  const store = createStateStore(statePath);
  await store.load();
  const requests = [];
  const handler = createMessageHandler({
    socket: {},
    flask: 'http://flask',
    logger: console,
    stateStore: store,
    bridgeSecret: 'shared-secret',
    fetchImpl: async (url, options) => {
      requests.push({ url, options });
      return { status: 200, ok: true, json: async () => ({ ok: true }) };
    },
  });

  await handler({
    key: { id: 'lid-map-message-1', remoteJid: '103860949528819@lid' },
    message: { conversation: '2' },
  });

  assert.strictEqual(JSON.parse(requests[0].options.body).phone, '919876543210');
  await unlink(statePath);
});

test('Authenticated /pair persists a LID mapping used by inbound replies', async () => {
  const statePath = `pair-test-${process.pid}-${Date.now()}`;
  const store = createStateStore(statePath);
  await store.load();
  const port = 32000 + (process.pid % 1000);
  const server = await createBridgeAPI({
    socket: {},
    bridgeSecret: 'shared-secret',
    stateStore: store,
    port,
  });
  if (!server.listening) {
    await new Promise((resolve) => server.once('listening', resolve));
  }
  try {
    const wrong = await fetch(`http://127.0.0.1:${port}/pair`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Bridge-Secret': 'wrong' },
      body: JSON.stringify({ lid: '103860949528819@lid', phone: '+91 98765-43210' }),
    });
    assert.strictEqual(wrong.status, 401);

    const paired = await fetch(`http://127.0.0.1:${port}/pair`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Bridge-Secret': 'shared-secret' },
      body: JSON.stringify({ lid: '103860949528819@lid', phone: '+91 98765-43210' }),
    });
    assert.strictEqual(paired.status, 200);

    const reloaded = createStateStore(statePath);
    await reloaded.load();
    assert.strictEqual(reloaded.getPhoneForLid('103860949528819@lid'), '919876543210');

    const requests = [];
    const handler = createMessageHandler({
      socket: {},
      flask: 'http://flask',
      logger: console,
      stateStore: reloaded,
      bridgeSecret: 'shared-secret',
      fetchImpl: async (url, options) => {
        requests.push({ url, options });
        return { status: 200, ok: true, json: async () => ({ ok: true }) };
      },
    });
    await handler({
      key: { id: 'paired-lid-message-1', remoteJid: '103860949528819@lid' },
      message: { conversation: '2' },
    });
    assert.strictEqual(JSON.parse(requests[0].options.body).phone, '919876543210');
  } finally {
    await new Promise((resolve) => server.close(resolve));
    await unlink(statePath);
  }
});

test('Unresolved @lid forwards raw JID and logs the full message key', async () => {
  const statePath = `lid-unresolved-test-${process.pid}-${Date.now()}`;
  const store = createStateStore(statePath);
  await store.load();
  const requests = [];
  const warnings = [];
  const key = {
    id: 'lid-unresolved-message-1',
    remoteJid: '103860949528819@lid',
    unusualField: 'visible-in-dump',
  };
  const handler = createMessageHandler({
    socket: {},
    flask: 'http://flask',
    logger: console,
    stateStore: store,
    bridgeSecret: 'shared-secret',
    fetchImpl: async (url, options) => {
      requests.push({ url, options });
      return { status: 200, ok: true, json: async () => ({ ok: true }) };
    },
  });

  const originalWarn = console.warn;
  console.warn = (line) => warnings.push(line);
  try {
    await handler({ key, message: { conversation: '2' } });
  } finally {
    console.warn = originalWarn;
  }

  assert.strictEqual(JSON.parse(requests[0].options.body).phone, key.remoteJid);
  assert.match(warnings[0], /"unusualField":"visible-in-dump"/);
  await unlink(statePath);
});

test('Self-pair response persists the LID and sends the verification reply', async () => {
  const statePath = `lid-self-pair-${process.pid}-${Date.now()}`;
  const store = createStateStore(statePath);
  await store.load();
  const sent = [];
  const handler = createMessageHandler({
    socket: { sendMessage: async (jid, message) => sent.push({ jid, message }) },
    flask: 'http://flask',
    logger: console,
    stateStore: store,
    bridgeSecret: 'shared-secret',
    fetchImpl: async () => ({
      status: 200,
      ok: true,
      json: async () => ({
        status: 'pair_donor',
        pair_phone: '919876543210',
        message: 'WhatsApp verified.',
      }),
    }),
  });

  await handler({
    key: { id: 'self-pair-message-1', remoteJid: '103860949528819@lid' },
    message: { conversation: '9876543210' },
  });

  assert.strictEqual(store.getPhoneForLid('103860949528819@lid'), '919876543210');
  assert.deepStrictEqual(sent, [{
    jid: '103860949528819@lid',
    message: { text: 'WhatsApp verified.' },
  }]);
  await unlink(statePath);
});

test('Bridge refuses to start without BRIDGE_SECRET', () => {
  assert.throws(() => requireBridgeSecret({}), /BRIDGE_SECRET is required/);
  const result = spawnSync(process.execPath, ['index.js'], {
    cwd: new URL('..', import.meta.url),
    env: { ...process.env, BRIDGE_SECRET: '' },
    encoding: 'utf8',
  });
  assert.strictEqual(result.status, 1);
  assert.match(result.stderr, /BRIDGE_SECRET startup error/);
});

// Test: Message ID deduplication
test('Message dedupe: same ID processed once', async (t) => {
  const store = createStateStore(':memory:');
  await store.load();

  const messageId = 'msg_123';
  assert.strictEqual(store.isProcessed(messageId), false, 'Message should not be processed initially');

  store.markProcessed(messageId);
  assert.strictEqual(store.isProcessed(messageId), true, 'Message should be marked as processed');

  // Try to process again; should be deduped
  const canProcess = !store.isProcessed(messageId);
  assert.strictEqual(canProcess, false, 'Message should be deduped on retry');
});

// Test: Reconnect on transient disconnect, not on loggedOut
test('Reconnect logic: retry on transient error, not on loggedOut', async (t) => {
  let reconnectCalled = false;
  let connectCount = 0;

  const bridge = createBridgeLifecycle({
    makeSocket: () => {
      connectCount++;
      return {
        ev: {
          on: (event, handler) => {
            if (event === 'connection.update' && connectCount === 1) {
              // Simulate transient disconnect (should retry)
              setTimeout(() => handler({
                connection: 'close',
                lastDisconnect: { error: { output: { statusCode: 0 } } }, // not loggedOut
              }), 10);
            }
            if (event === 'creds.update') return;
            if (event === 'messages.upsert') return;
          },
        },
        updateMediaMessage: () => {},
      };
    },
    createHandler: () => async () => {},
    saveCreds: () => {},
    loggedOutStatus: 401, // DisconnectReason.loggedOut
    checkFlask: () => Promise.resolve(),
    showQr: () => {},
    log: { log: () => {}, error: () => {} },
    schedule: (fn, delay) => setTimeout(fn, Math.min(delay, 50)), // Fast retry for test
  });

  bridge.connect();
  await new Promise((r) => setTimeout(r, 200)); // Wait for reconnect to be scheduled

  assert.ok(connectCount >= 1, 'Should have attempted at least one connection');
});

// Test: Do not reconnect on loggedOut
test('No reconnect on loggedOut status', async (t) => {
  let connectCount = 0;

  const bridge = createBridgeLifecycle({
    makeSocket: () => {
      connectCount++;
      return {
        ev: {
          on: (event, handler) => {
            if (event === 'connection.update' && connectCount === 1) {
              // Simulate loggedOut disconnect
              setTimeout(() => handler({
                connection: 'close',
                lastDisconnect: { error: { output: { statusCode: 401 } } }, // loggedOut
              }), 10);
            }
            if (event === 'creds.update') return;
            if (event === 'messages.upsert') return;
          },
        },
        updateMediaMessage: () => {},
      };
    },
    createHandler: () => async () => {},
    saveCreds: () => {},
    loggedOutStatus: 401,
    checkFlask: () => Promise.resolve(),
    showQr: () => {},
    log: { log: () => {}, error: () => {} },
    schedule: (fn, delay) => setTimeout(fn, 50),
  });

  bridge.connect();
  await new Promise((r) => setTimeout(r, 200));

  assert.strictEqual(connectCount, 1, 'Should not reconnect after loggedOut');
});
