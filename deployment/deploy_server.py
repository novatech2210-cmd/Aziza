import os
import pexpect
import sys

SSH_HOST = os.environ.get("AZIZA_SSH_HOST", "")
SSH_PASS = os.environ.get("AZIZA_SSH_PASS", "")

child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no aziza@{SSH_HOST}', encoding='utf-8')
child.logfile = sys.stdout

child.expect('password:')
child.sendline(SSH_PASS)

child.expect(r'\$')
child.sendline('sudo mkdir -p /workspace/_src')
child.expect('password for aziza:')
child.sendline(SSH_PASS)

child.expect(r'\$')
child.sendline('sudo chown -R aziza:aziza /workspace')

child.expect(r'\$')
child.sendline('cd /workspace/_src')

child.expect(r'\$')
child.sendline('rm -rf AZIZA-Remote-Build')

child.expect(r'\$')
child.sendline('git clone https://github.com/novatech2210-cmd/AZIZA-Remote-Build.git')

child.expect(r'\$')
child.sendline('cd AZIZA-Remote-Build/deploy/vps')

child.expect(r'\$')
child.sendline('chmod +x bootstrap.sh deploy-all.sh')

child.expect(r'\$')
child.sendline('echo "Setup commands delivered successfully."')

child.expect(r'\$')
child.sendline('exit')
child.expect(pexpect.EOF)
