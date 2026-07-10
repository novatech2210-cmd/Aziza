const WebSocket = require('ws');

const BASE = 'ws://127.0.0.1:3000';

function test(lang, msg, label) {
  return new Promise((resolve, reject) => {
    const sid = 'test-' + Date.now() + Math.floor(Math.random() * 1000);
    const ws = new WebSocket(BASE + '/ws/chat-text?sessionId=' + sid + '&token=test');
    const tokens = [];
    let timer = setTimeout(() => {
      ws.close();
      reject(new Error(label + ': timeout after 30s'));
    }, 30000);

    ws.on('open', () => {
      ws.send(JSON.stringify({ type: 'message', message: msg, language: lang }));
    });

    ws.on('message', (raw) => {
      try {
        const d = JSON.parse(raw);
        if (d.type === 'token') { tokens.push(d.content); process.stdout.write(d.content); }
        if (d.type === 'done') {
          clearTimeout(timer);
          ws.close();
          console.log('\n[' + label + '] OK — tokens: ' + tokens.length + ', preview: ' + tokens.join('').slice(0,80));
          resolve();
        }
        if (d.type === 'error') {
          clearTimeout(timer);
          ws.close();
          reject(new Error(label + ': server error: ' + d.message));
        }
      } catch {}
    });

    ws.on('error', (e) => { clearTimeout(timer); reject(new Error(label + ': ws error: ' + e.message)); });
  });
}

(async () => {
  try {
    await test('en', 'hi', 'English');
    console.log('\nAll tests passed.');
    process.exit(0);
  } catch(e) {
    console.error('\nFAIL:', e.message);
    process.exit(1);
  }
})();
