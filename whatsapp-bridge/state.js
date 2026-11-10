import { readFile, writeFile } from 'node:fs/promises';

export function createStateStore(path) {
  let state = { processedMessageIds: new Set() };

  return {
    isProcessed(messageId) {
      return state.processedMessageIds.has(messageId);
    },

    markProcessed(messageId) {
      state.processedMessageIds.add(messageId);
    },

    async save() {
      await writeFile(path, JSON.stringify({
        processedMessageIds: Array.from(state.processedMessageIds),
      }));
    },

    async load() {
      try {
        const data = JSON.parse(await readFile(path, 'utf8'));
        state.processedMessageIds = new Set(data.processedMessageIds || []);
      } catch {
        // File doesn't exist or is invalid; start fresh
        state.processedMessageIds = new Set();
      }
    },
  };
}
