import sys

filename = '/root/aziza-build/backend/services/orchestrator/core.py'
with open(filename, 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'await self.session_manager.ensure_session(session_id, params=params)' in line:
        # We swap the next line "await self._route_session(session_id)" with this one, and add a sleep.
        pass

# A simpler replacement:
with open(filename, 'r') as f:
    content = f.read()

content = content.replace(
    '            await self.session_manager.ensure_session(session_id, params=params)\n            await self._route_session(session_id)',
    '            await self._route_session(session_id)\n            await asyncio.sleep(0.5)\n            await self.session_manager.ensure_session(session_id, params=params)'
)

with open(filename, 'w') as f:
    f.write(content)

