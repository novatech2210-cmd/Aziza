import os
import pexpect
import sys

HOST = os.environ.get("AZIZA_SSH_HOST", "")
PASS = os.environ.get("AZIZA_SSH_PASS", "")
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

    print("\n\n--- CHECKING FOR DATASET ---")
    ssh.sendline('ls -la /root/aziza-build/aziza-bilingual.jsonl')
    ssh.expect(r'#', timeout=10)

    print("\n\n--- STARTING RUSSIAN TRAINING ---")
    script = '/root/aziza-build/train_russian.py'
    log = '/root/aziza-build/logs/train_russian.log'
    dataset = '/root/aziza-build/aziza-bilingual.jsonl'
    hf_token = os.environ.get("HF_TOKEN", "")
    if not hf_token:
        raise RuntimeError("HF_TOKEN environment variable not set")
    cmd = f'cd /root/aziza-build && export HF_TOKEN={hf_token} && /root/aziza-build/venv/bin/python3 {script} --dataset_path {dataset} 2>&1 | tee {log}'
    
    # Kill if exists
    ssh.sendline('tmux kill-session -t russian 2>/dev/null')
    ssh.expect(r'#', timeout=10)

    ssh.sendline(f"tmux new-session -d -s russian bash -c \"{cmd}\"")
    ssh.expect(r'#', timeout=10)

    print("\n\n--- TMUX SESSIONS ---")
    ssh.sendline('tmux ls')
    ssh.expect(r'#', timeout=10)
    
    print("\n\n--- WAIT AND CHECK RUSSIAN LOGS ---")
    import time
    time.sleep(10)
    ssh.sendline('tail -n 30 /root/aziza-build/logs/train_russian.log')
    ssh.expect(r'#', timeout=20)

    ssh.sendline('exit')
    ssh.expect(r'\$', timeout=10)
    ssh.sendline('exit')
    ssh.expect(pexpect.EOF, timeout=10)

if __name__ == "__main__":
    run()
