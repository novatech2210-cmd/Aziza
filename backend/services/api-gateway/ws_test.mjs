/**
 * Smoke-test: send one Russian and one Uzbek message through the
 * api-gateway WebSocket and verify token + done events are received.
 * Run from: /root/aziza-build/backend/services/api-gateway/
 * Command:  node ws_test.mjs
 */
import WebSocket from 'ws';

const BASE = 'ws://localhost:8080';
const CHAT_PATH = '/api/chat-text';

function test(lang, msg, label) {
  return new Promise((resolve, reject) => {
    const sid = 'smoke-' + Date.now();
    const ws = new WebSocket(`${BASE}${CHAT_PATH}?sessionId=${sid}`);
    const tokens = [];
    const timer = setTimeout(() => {
      ws.close();
      reject(new Error(`${label}: timeout after 60s`));
    }, 60000);

    ws.on('open', () => {
      // Gateway expects { message: string, language: string }
      ws.send(JSON.stringify({ message: msg, language: lang }));
    });

    ws.on('message', (raw) => {
      try {
        const d = JSON.parse(raw.toString());
        if (d.type === 'token') { tokens.push(d.content); process.stdout.write('.'); }
        if (d.type === 'done') {
          clearTimeout(timer);
          ws.close();
          const preview = tokens.join('').slice(0, 80);
          console.log(`\n[${label}] PASS — ${tokens.length} tokens | "${preview}"`);
          resolve();
        }
        if (d.type === 'error') {
          clearTimeout(timer);
          ws.close();
          reject(new Error(`${label}: server error → ${d.message}`));
        }
      } catch {}
    });

    ws.on('error', (e) => {
      clearTimeout(timer);
      reject(new Error(`${label}: ws error → ${e.message}`));
    });
  });
}

try {
  await test('ru', 'Привет', 'Russian');
  await test('uz', 'Salom', 'Uzbek');
  console.log('\nAll tests passed.');
  process.exit(0);
} catch (e) {
  console.error('\nFAIL:', e.message);
  process.exit(1);
}
