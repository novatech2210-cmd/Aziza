import os
import pexpect
import sys

SSH_HOST = os.environ.get("AZIZA_SSH_HOST", "")
SSH_PASS = os.environ.get("AZIZA_SSH_PASS", "")

command = sys.argv[1]

child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no aziza@{SSH_HOST}', encoding='utf-8')
child.expect('password:')
child.sendline(SSH_PASS)
child.expect(r'\$')
child.sendline('sudo su -')
child.expect('password for aziza:')
child.sendline(SSH_PASS)
child.expect('# ')
child.sendline(command)
child.expect('# ')
print(child.before)
child.sendline('exit')
child.expect(r'\$')
child.sendline('exit')
child.expect(pexpect.EOF)
