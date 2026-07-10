import os
import pexpect
import sys

SSH_HOST = os.environ.get("AZIZA_SSH_HOST", "")
SSH_PASS = os.environ.get("AZIZA_SSH_PASS", "")

child = pexpect.spawn(f'scp -o StrictHostKeyChecking=no /home/kali/Desktop/AZIZA-BUILD/backend/services/api-gateway/src/gateway/chat.gateway.ts aziza@{SSH_HOST}:/tmp/chat.gateway.ts', encoding='utf-8')
child.expect('password:')
child.sendline(SSH_PASS)
child.expect(pexpect.EOF)

child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no aziza@{SSH_HOST}', encoding='utf-8')
child.expect('password:')
child.sendline(SSH_PASS)
child.expect(r'\$')

child.sendline('sudo su -')
index = child.expect(['password for aziza:', r'root@aziza-worker-01:~#'])
if index == 0:
    child.sendline(SSH_PASS)
    child.expect(r'#')

child.sendline('cp /tmp/chat.gateway.ts /root/aziza-build/backend/services/api-gateway/src/gateway/chat.gateway.ts')
child.expect(r'#')

child.sendline('cd /root/aziza-build/backend/services/api-gateway')
child.expect(r'#')

child.sendline('npm run build')
child.expect(r'#', timeout=120)

child.sendline('pm2 restart api-gateway')
child.expect(r'#')

child.sendline('pm2 list')
child.expect(r'#')
print(child.before)

child.sendline('exit')
child.expect(r'\$')
child.sendline('exit')
child.expect(pexpect.EOF)
