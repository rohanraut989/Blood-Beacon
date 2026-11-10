import { readFile, writeFile } from 'node:fs/promises';

export function createStateStore(path) {
  let state = { processedMessageIds: new Set(), lidToPhone: {} };

  return {
    isProcessed(messageId) {
      return state.processedMessageIds.has(messageId);
    },

    markProcessed(messageId) {
      state.processedMessageIds.add(messageId);
    },

    getPhoneForLid(lid) {
      return state.lidToPhone[lid] || state.lidToPhone[String(lid).split('@')[0]];
    },

    setLidPhone(lid, phone) {
      const key = String(lid).split('@')[0].replace(/\D/g, '');
      const normalizedPhone = String(phone).replace(/\D/g, '');
      if (!key || !normalizedPhone) throw new Error('LID and phone must contain digits');
      state.lidToPhone[key] = normalizedPhone;
    },

    async save() {
      await writeFile(path, JSON.stringify({
        processedMessageIds: Array.from(state.processedMessageIds),
        lidToPhone: state.lidToPhone,
      }));
    },

    async load() {
      try {
        const data = JSON.parse(await readFile(path, 'utf8'));
        state.processedMessageIds = new Set(data.processedMessageIds || []);
        state.lidToPhone = data.lidToPhone || {};
      } catch {
        // File doesn't exist or is invalid; start fresh
        state.processedMessageIds = new Set();
        state.lidToPhone = {};
      }
    },
  };
}
