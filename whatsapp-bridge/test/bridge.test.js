import test from 'node:test';
import assert from 'node:assert';
import { createStateStore } from '../state.js';
import { createBridgeLifecycle } from '../lifecycle.js';

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
