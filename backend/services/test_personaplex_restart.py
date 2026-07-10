import requests
import time

URL = 'http://localhost:8000'
SESSION_ID = 'test_retention_restart'

print('Sending messages...')
requests.post(f'{URL}/sessions/memory', json={'session_id': SESSION_ID, 'content': 'Message 1', 'sender': 'user'})
requests.post(f'{URL}/sessions/memory', json={'session_id': SESSION_ID, 'content': 'Message 2', 'sender': 'user'})

res = requests.get(f'{URL}/sessions/{SESSION_ID}/context')
history = res.json().get('history', [])
print('Context before restart:', len(history), 'messages')

