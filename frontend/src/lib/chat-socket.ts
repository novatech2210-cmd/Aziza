/**
 * FIXED frontend client for the /api/chat-text gateway.
 *
 * The backend gateway is registered with `@nestjs/platform-ws` (raw `ws`
 * library), so Socket.IO clients cannot connect — they hit 404 on
 * `/socket.io/?EIO=4&transport=polling`. Two equivalent fixes:
 *
 *   Option A (recommended, used here): keep the backend on raw `ws` and
 *   switch the frontend to a plain WebSocket.
 *
 *   Option B: keep the frontend on Socket.IO and switch the backend to
 *   `@nestjs/platform-socket.io` by setting
 *   `app.useWebSocketAdapter(new IoAdapter(app))` in `main.ts`.
 *
 * Option A is simpler and removes the `socket.io` dependency from the
 * frontend bundle. Below is the drop-in replacement for the
 * `io('http://localhost:8080/api/chat-text')` snippet from the transcript.
 */

// Frontend connects to:
const socket = new WebSocket('ws://localhost:8080/api/chat-text');

// Send a message:
socket.addEventListener('open', () => {
  socket.send(
    JSON.stringify({
      message: 'Hello!',
      language: 'auto', // or 'en', 'ru', 'uz', 'uz_cyrillic', ...
    }),
  );
});

// Receive responses:
socket.addEventListener('message', (event) => {
  let data;
  try {
    data = JSON.parse(event.data);
  } catch {
    return;
  }

  switch (data.type) {
    case 'ready':
      // server acks the connection
      break;
    case 'pong':
      // heartbeat response
      break;
    case 'token':
      break;
    case 'done':
      break;
    case 'error':
      console.error('[ChatSocket]', data.message);
      break;
  }
});

socket.addEventListener('close', () => {
});

// Optional heartbeat to keep proxies happy:
setInterval(() => {
  if (socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: 'ping' }));
  }
}, 30000);

export { socket };
