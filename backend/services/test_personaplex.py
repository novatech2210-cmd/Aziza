import requests
import time

URL = 'http://localhost:8000'
SESSION_ID = 'test_retention_123'

# Send message
res = requests.post(f'{URL}/sessions/memory', json={
    'session_id': SESSION_ID,
    'content': 'Hello, testing memory retention.',
    'sender': 'user'
})
print('Store memory:', res.json())

# Get context
res = requests.get(f'{URL}/sessions/{SESSION_ID}/context')
history = res.json().get('history', [])
print('Context before restart:', len(history), 'messages')

