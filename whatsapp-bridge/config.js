import { readFileSync } from 'node:fs';

export function requireBridgeSecret(env = process.env) {
  let secret = env.BRIDGE_SECRET;
  if (!secret && env === process.env) {
    try {
      const dotenv = readFileSync(new URL('./.env', import.meta.url), 'utf8');
      secret = dotenv
        .split(/\r?\n/)
        .find((line) => line.trim().startsWith('BRIDGE_SECRET='))
        ?.split('=').slice(1).join('=').trim();
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
  }
  if (!secret) {
    throw new Error('BRIDGE_SECRET is required; refusing to start without a shared bridge secret');
  }
  return secret;
}
