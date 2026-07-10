const WebSocket = require('ws');
const ws = new WebSocket('ws://127.0.0.1:3000/api/chat-text?sessionId=test-12345');

ws.on('open', () => {
  console.log('Connected to ws://127.0.0.1:3000/api/chat-text');
  
  // Send a test message in Russian
  const msg = {
    message: "Салом, қандайсиз?",
    language: "uz_cyrillic"
  };
  ws.send(JSON.stringify(msg));
  console.log('Sent message:', msg);
});

ws.on('message', (data) => {
  try {
    const parsed = JSON.parse(data.toString());
    if (parsed.type === 'token') {
      process.stdout.write(parsed.content);
    } else if (parsed.type === 'done') {
      console.log('\n[Done received]');
      ws.close();
    } else {
      console.log('\n[Other message]:', parsed);
    }
  } catch (err) {
    console.log('\nRaw data:', data.toString());
  }
});

ws.on('error', (err) => {
  console.error('Connection Error:', err.message);
});

ws.on('close', (code, reason) => {
  console.log('\nConnection Closed:', code, reason.toString());
});
