import os
import pexpect
import sys
import time

def run_remote_command(host, user, password, command):
    print(f"Connecting to {host}...")
    child = pexpect.spawn(f"ssh -o StrictHostKeyChecking=no {user}@{host}", encoding='utf-8')
    
    index = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=10)
    if index == 0:
        child.sendline(password)
    elif index == 1:
        print("EOF reached")
        print(child.before)
        return
    else:
        print("Timeout reached")
        print(child.before)
        return
        
    child.expect(['$ ', '# ', 'aziza@'], timeout=10)
    
    print(f"Running command: {command}")
    child.sendline(command)
    child.expect(['$ ', '# ', 'aziza@'], timeout=120)
    print(child.before)
    
    child.sendline('exit')
    child.expect(pexpect.EOF)

if __name__ == '__main__':
    command = sys.argv[1]
    run_remote_command(os.environ.get("AZIZA_SSH_HOST", ""), 'aziza', os.environ.get("AZIZA_SSH_PASS", ""), command)
