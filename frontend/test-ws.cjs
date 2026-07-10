const WebSocket = require('ws');
const ws = new WebSocket('ws://localhost:5173/api/chat?sessionId=test-123');

ws.on('open', () => {
  console.log('Connected to ws://localhost:5173/api/chat');
  ws.close();
});

ws.on('error', (err) => {
  console.error('Connection Error:', err.message);
});

ws.on('close', (code, reason) => {
  console.log('Connection Closed:', code, reason.toString());
});

const ws2 = new WebSocket('ws://localhost:8080/api/chat?sessionId=test-123');

ws2.on('open', () => {
  console.log('Connected directly to ws://localhost:8080/api/chat');
  ws2.close();
});

ws2.on('error', (err) => {
  console.error('Direct Connection Error:', err.message);
});

ws2.on('close', (code, reason) => {
  console.log('Direct Connection Closed:', code, reason.toString());
});
