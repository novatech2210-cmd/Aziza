import os
import pexpect
import sys

SSH_HOST = os.environ.get("AZIZA_SSH_HOST", "")
SSH_PASS = os.environ.get("AZIZA_SSH_PASS", "")
HOST = f'aziza@{SSH_HOST}'
PASS = SSH_PASS
SSH_OPTS = '-o StrictHostKeyChecking=no'

def run():
    print("Connecting to server...")
    ssh = pexpect.spawn(f'ssh {SSH_OPTS} {HOST}', encoding='utf-8', timeout=30)
    ssh.logfile = sys.stdout

    idx = ssh.expect(['password:', r'\$', pexpect.TIMEOUT], timeout=10)
    if idx == 0:
        ssh.sendline(PASS)
        ssh.expect(r'\$', timeout=20)
    
    print("\n\n--- ESCALATING PRIVILEGES ---")
    ssh.sendline('sudo su')
    idx = ssh.expect(['password for aziza:', r'#', pexpect.TIMEOUT], timeout=10)
    if idx == 0:
        ssh.sendline(PASS)
        ssh.expect(r'#', timeout=20)

    print("\n\n--- NVIDIA SMI ---")
    ssh.sendline('nvidia-smi')
    ssh.expect(r'#', timeout=20)

    print("\n\n--- TMUX SESSIONS ---")
    ssh.sendline('tmux ls')
    ssh.expect(r'#', timeout=20)

    print("\n\n--- UZ LATIN LOGS ---")
    ssh.sendline('tail -n 30 /root/aziza-build/logs/train_uz_latin.log')
    ssh.expect(r'#', timeout=20)

    print("\n\n--- UZ CYRILLIC LOGS ---")
    ssh.sendline('tail -n 30 /root/aziza-build/logs/train_uz_cyrillic.log')
    ssh.expect(r'#', timeout=20)

    print("\n\n--- RUSSIAN LOGS ---")
    ssh.sendline('tail -n 30 /root/aziza-build/logs/train_russian.log')
    ssh.expect(r'#', timeout=20)

    ssh.sendline('exit')
    ssh.expect(r'\$', timeout=10)
    ssh.sendline('exit')
    ssh.expect(pexpect.EOF, timeout=10)

if __name__ == "__main__":
    run()
