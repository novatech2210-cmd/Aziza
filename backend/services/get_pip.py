import os
import pexpect

SSH_HOST = os.environ.get("AZIZA_SSH_HOST", "")
SSH_PASS = os.environ.get("AZIZA_SSH_PASS", "")

with open('output_pip.txt', 'w') as f:
    try:
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o PubkeyAuthentication=no -o PreferredAuthentications=password aziza@{SSH_HOST}', encoding='utf-8', timeout=10)
        child.logfile_read = f
        child.expect('(?i)password:')
        child.sendline(SSH_PASS)
        child.expect(r'\$')
        
        child.sendline('sudo su -')
        child.expect('(?i)password')
        child.sendline(SSH_PASS)
        child.expect('#')
        
        child.sendline('source /root/aziza-build/venv/bin/activate')
        child.expect('#')
        
        child.sendline('pip show torch')
        child.expect('#')
        
        child.sendline('exit')
    except Exception as e:
        print('Error:', e)
