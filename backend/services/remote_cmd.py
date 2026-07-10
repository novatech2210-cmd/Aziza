import os
import pexpect
import sys

def run_remote_cmd(host, user, password, cmd):
    try:
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {user}@{host}', encoding='utf-8', timeout=30)
        # We might need to wait for password prompt
        i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT])
        if i == 0:
            child.sendline(password)
        else:
            print("Failed to login")
            return
        
        # Wait for prompt
        child.expect(r'\$')
        
        # Run command
        child.sendline(cmd)
        
        # Wait for prompt again
        child.expect(r'\$')
        
        print("--- COMMAND OUTPUT ---")
        print(child.before)
        print("----------------------")
        
        child.sendline('exit')
        child.expect(pexpect.EOF)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_remote_cmd(os.environ.get("AZIZA_SSH_HOST", ""), 'aziza', os.environ.get("AZIZA_SSH_PASS", ""), sys.argv[1])
