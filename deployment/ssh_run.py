import os
import sys
import pexpect

if len(sys.argv) < 2:
    print("Usage: python ssh_run.py <command>")
    sys.exit(1)

cmd = sys.argv[1]

child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no aziza@{os.environ.get("AZIZA_SSH_HOST", "")}', encoding='utf-8', timeout=15)
idx = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT])
if idx == 0:
    child.sendline(os.environ.get("AZIZA_SSH_PASS", ""))
    child.expect(r'\$')
    
    # Run the command
    child.sendline(cmd)
    
    # Wait for the prompt again or sudo password
    idx = child.expect([r'\[sudo\] password for', r'\$', pexpect.EOF, pexpect.TIMEOUT], timeout=30)
    if idx == 0:
        child.sendline(os.environ.get("AZIZA_SSH_PASS", ""))
        idx = child.expect([r'\$', pexpect.EOF, pexpect.TIMEOUT], timeout=30)
    
    # Print what happened between the command and the prompt
    # The output includes the command itself and the output
    print(child.before)
else:
    print("Failed to login.")
