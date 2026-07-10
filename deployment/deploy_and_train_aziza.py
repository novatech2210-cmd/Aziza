#!/usr/bin/env python3
"""
deploy_and_train_aziza.py — Deploy and launch Uzbek training via the aziza user.
Syncs to ~aziza, then uses sudo to copy to /root/aziza-build and launch.
"""
import os
import pexpect
import sys
import time

HOST = os.environ.get("AZIZA_SSH_HOST", "")
PASS = os.environ.get("AZIZA_SSH_PASS", "")
LOCAL = '/home/kali/Desktop/AZIZA-BUILD/'
REMOTE_TMP = '/home/aziza/AZIZA-BUILD-SYNC/'
SSH_OPTS = '-o StrictHostKeyChecking=no -o ConnectTimeout=20 -o ServerAliveInterval=60'

def log(msg):
    print(f'\n{"="*60}\n{msg}\n{"="*60}')

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — rsync to ~aziza
# ─────────────────────────────────────────────────────────────────────────────
log('STEP 1: rsync → /home/aziza/AZIZA-BUILD-SYNC/')

# Create the remote tmp dir first
mkdir_cmd = f'ssh {SSH_OPTS} {HOST} "mkdir -p {REMOTE_TMP}"'
child = pexpect.spawn('/bin/bash', ['-c', mkdir_cmd], encoding='utf-8', timeout=60)
idx = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=20)
if idx == 0:
    child.sendline(PASS)
    child.expect(pexpect.EOF, timeout=20)

rsync_cmd = (
    f'rsync -avz --progress '
    f'--exclude ".git" --exclude "__pycache__" --exclude "*.pyc" '
    f'--exclude "node_modules" --exclude "venv" --exclude "*.log" '
    f'--exclude ".gemini" --exclude "adapters" --exclude "*.safetensors" '
    f'-e "ssh {SSH_OPTS}" '
    f'{LOCAL} {HOST}:{REMOTE_TMP}'
)
child = pexpect.spawn('/bin/bash', ['-c', rsync_cmd], encoding='utf-8', timeout=3600)
child.logfile = sys.stdout

idx = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=30)
if idx == 0:
    child.sendline(PASS)
    child.expect(pexpect.EOF, timeout=3600)

print('\n✅ Rsync complete.\n')

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — SSH as aziza and do sudo operations
# ─────────────────────────────────────────────────────────────────────────────
log('STEP 2: SSH into server as aziza')

ssh = pexpect.spawn(
    f'ssh {SSH_OPTS} {HOST}',
    encoding='utf-8',
    timeout=120,
)
ssh.logfile = sys.stdout

def wait(patterns=None, timeout=30):
    if patterns is None:
        patterns = [r'\$\s*$', r'#\s*$']
    return ssh.expect(patterns + [pexpect.TIMEOUT], timeout=timeout)

def sudo_cmd(cmd, timeout=30):
    ssh.sendline(f"sudo -S bash -c '{cmd}'")
    idx = ssh.expect([r'\[sudo\] password for', r'\$\s*$', r'#\s*$'], timeout=timeout)
    if idx == 0:
        ssh.sendline(PASS)
        wait(timeout=timeout)
    # If already had sudo privs, it will match prompt when the command is done

# Authenticate
idx = ssh.expect(['password:', r'\$', r'Last login', pexpect.TIMEOUT], timeout=20)
if idx == 0:
    ssh.sendline(PASS)
    wait(timeout=30)
elif idx == 2:  # Last login banner
    wait(timeout=30)

# Sync from tmp to /root/aziza-build
log('STEP 3: Sync to /root/aziza-build')
sudo_cmd(f"mkdir -p /root/aziza-build && rsync -a {REMOTE_TMP} /root/aziza-build/")

# ── Make logs dir ─────────────────────────────────────────────────────────────
sudo_cmd('mkdir -p /root/aziza-build/logs && echo LOGS_DIR_OK')

# ── Python + pip check ───────────────────────────────────────────────────────
sudo_cmd('python3 --version && pip3 --version')

# ── Install / upgrade training deps ──────────────────────────────────────────
log('STEP 4: Installing training dependencies in venv')
sudo_cmd('python3 -m venv /root/aziza-build/venv && echo VENV_CREATED')
sudo_cmd(
    '/root/aziza-build/venv/bin/pip install --upgrade '
    '--index-url https://download.pytorch.org/whl/cu118 torch',
    timeout=600
)
sudo_cmd(
    '/root/aziza-build/venv/bin/pip install --upgrade '
    'transformers peft trl bitsandbytes datasets accelerate trackio huggingface_hub',
    timeout=600
)

# ── Kill any stale training sessions ─────────────────────────────────────────
log('STEP 5: Resetting tmux sessions')
sudo_cmd('tmux kill-session -t uz-latin 2>/dev/null; tmux kill-session -t uz-cyrillic 2>/dev/null; echo SESSIONS_CLEARED')

# ── Launch Uzbek Latin training ───────────────────────────────────────────────
log('STEP 6: Launch uz-latin training in tmux (as root)')
latin_script = '/root/aziza-build/train_uzbek_latin_hf.py'
latin_log    = '/root/aziza-build/logs/train_uz_latin.log'
latin_cmd    = f'cd /root/aziza-build && export HF_TOKEN=$HF_TOKEN && /root/aziza-build/venv/bin/python3 {latin_script} 2>&1 | tee {latin_log}'

sudo_cmd(f"tmux new-session -d -s uz-latin bash -c \"{latin_cmd}\" && echo LATIN_LAUNCHED")

# ── Launch Uzbek Cyrillic training ────────────────────────────────────────────
log('STEP 7: Launch uz-cyrillic training in tmux (as root)')
cyrillic_script = '/root/aziza-build/train_uzbek_cyrillic_hf.py'
cyrillic_log    = '/root/aziza-build/logs/train_uz_cyrillic.log'
cyrillic_cmd    = f'cd /root/aziza-build && export HF_TOKEN=$HF_TOKEN && /root/aziza-build/venv/bin/python3 {cyrillic_script} 2>&1 | tee {cyrillic_log}'

sudo_cmd(f"tmux new-session -d -s uz-cyrillic bash -c \"{cyrillic_cmd}\" && echo CYRILLIC_LAUNCHED")

# ── Verify sessions ───────────────────────────────────────────────────────────
sudo_cmd('tmux ls && echo ALL_SESSIONS_UP')

# Wait 20s and check logs
print('\nWaiting 20 seconds for scripts to start...')
time.sleep(20)

sudo_cmd(f'echo "=== LATIN LOG (first 40 lines) ===" && head -40 {latin_log} 2>/dev/null || echo "No log yet"')
sudo_cmd(f'echo "=== CYRILLIC LOG (first 40 lines) ===" && head -40 {cyrillic_log} 2>/dev/null || echo "No log yet"')

# ── Final summary ─────────────────────────────────────────────────────────────
sudo_cmd('nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader')

ssh.sendline('exit')
ssh.expect(pexpect.EOF, timeout=15)

log('✅ DEPLOY + TRAINING LAUNCH COMPLETE')
print(f"""
Monitor sessions on server:
  ssh aziza@{os.environ.get("AZIZA_SSH_HOST", "")}
  sudo tmux attach -t uz-latin        # Uzbek Latin training
  sudo tmux attach -t uz-cyrillic     # Uzbek Cyrillic training

Tail logs:
  sudo tail -f /root/aziza-build/logs/train_uz_latin.log
  sudo tail -f /root/aziza-build/logs/train_uz_cyrillic.log

Adapters push to HuggingFace Hub on each checkpoint save.
""")
