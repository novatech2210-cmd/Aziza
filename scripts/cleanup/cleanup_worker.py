import os
import pexpect
import sys
import time

SSH_HOST = os.environ.get("AZIZA_SSH_HOST", "")
SSH_PASS = os.environ.get("AZIZA_SSH_PASS", "")

child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no aziza@{SSH_HOST}', encoding='utf-8', timeout=30)
child.logfile = sys.stdout
idx = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT])
if idx == 0:
    child.sendline(SSH_PASS)
    idx2 = child.expect([r'aziza@aziza-worker-01', 'Permission denied', pexpect.EOF, pexpect.TIMEOUT])
    if idx2 == 0:
        time.sleep(1)
        child.sendline('rm -rf /home/aziza/.cache/huggingface')
        child.expect(r'aziza@aziza-worker-01')
        
        child.sendline('rm -rf /home/aziza/.cache/pip')
        child.expect(r'aziza@aziza-worker-01')

        child.sendline('df -h')
        child.expect(r'aziza@aziza-worker-01')

        child.sendline('sudo rm -rf /root/.cache/huggingface')
        idx3 = child.expect(['password for aziza:', r'aziza@aziza-worker-01', pexpect.EOF, pexpect.TIMEOUT])
        if idx3 == 0:
            child.sendline(SSH_PASS)
            child.expect(r'aziza@aziza-worker-01')

        child.sendline('df -h')
        child.expect(r'aziza@aziza-worker-01')
        
        child.sendline('exit')
    else:
        print('Failed to login.')
else:
    print('Failed to prompt for password.')
