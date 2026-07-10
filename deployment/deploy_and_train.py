#!/usr/bin/env python3
"""
deploy_and_train.py — Resync code to /root/aziza-build and launch
Uzbek Latin + Cyrillic QLoRA training in parallel tmux sessions.
"""
import os
import pexpect
import sys
import time

PASS = os.environ.get("AZIZA_SSH_PASS", "")
HOST = f'aziza@{os.environ.get("AZIZA_SSH_HOST", "")}'
LOCAL = '/home/kali/Desktop/AZIZA-BUILD/'
REMOTE = '/root/aziza-build/'

SSH_OPTS = '-o StrictHostKeyChecking=no -o ConnectTimeout=20 -o ServerAliveInterval=30'

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def ssh_cmd(command: str, timeout: int = 60) -> str:
    """Run a single command over SSH and return output."""
    full = f'ssh {SSH_OPTS} {HOST} "{command}"'
    child = pexpect.spawn('/bin/bash', ['-c', full], encoding='utf-8', timeout=timeout)
    child.logfile_read = sys.stdout
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=20)
    if i == 0:
        child.sendline(PASS)
        child.expect(pexpect.EOF, timeout=timeout)
    return child.before or ''


def wait_prompt(child, timeout=30):
    child.expect([r'\$', r'#'], timeout=timeout)


# ─────────────────────────────────────────────────────────────────────────────
# Step 1: rsync
# ─────────────────────────────────────────────────────────────────────────────
print('\n' + '='*60)
print('STEP 1: rsync → /root/aziza-build/')
print('='*60)

rsync_cmd = (
    f'rsync -avz --progress '
    f'--exclude ".git" --exclude "__pycache__" --exclude "*.pyc" '
    f'--exclude "node_modules" --exclude "venv" --exclude "*.log" '
    f'--exclude ".gemini" '
    f'-e "ssh {SSH_OPTS}" '
    f'{LOCAL} {HOST}:{REMOTE}'
)
child = pexpect.spawn('/bin/bash', ['-c', rsync_cmd], encoding='utf-8', timeout=3600)
child.logfile = sys.stdout
i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=30)
if i == 0:
    child.sendline(PASS)
    child.expect(pexpect.EOF, timeout=3600)

print('\n✅ Rsync complete.\n')

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: SSH session — setup + launch training
# ─────────────────────────────────────────────────────────────────────────────
print('='*60)
print('STEP 2: Launch training on server')
print('='*60)

child = pexpect.spawn(
    f'ssh {SSH_OPTS} {HOST}',
    encoding='utf-8', timeout=60
)
child.logfile = sys.stdout
i = child.expect(['password:', r'\$', r'#', 'Last login'], timeout=30)
if i == 0:
    child.sendline(PASS)
    wait_prompt(child, 30)
elif i == 3:  # Last login banner
    wait_prompt(child, 30)

# ── Fix ownership so aziza user can write ────────────────────────────────────
print('\n--- Fixing /root/aziza-build ownership ---')
child.sendline('sudo chown -R $USER:$USER /root/aziza-build 2>/dev/null || true')
i = child.expect(['password for', r'\$', r'#'], timeout=20)
if i == 0:
    child.sendline(PASS)
    wait_prompt(child, 30)

# ── Check GPU ────────────────────────────────────────────────────────────────
print('\n--- GPU status ---')
child.sendline('nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader')
wait_prompt(child, 15)

# ── Check / install pip deps ─────────────────────────────────────────────────
print('\n--- Checking Python env ---')
child.sendline('python3 -c "import torch; print(torch.__version__, torch.cuda.is_available())" 2>&1 || echo NO_TORCH')
wait_prompt(child, 30)

child.sendline('python3 -c "import trl; print(trl.__version__)" 2>&1 || echo NO_TRL')
wait_prompt(child, 15)

# Install deps if missing
print('\n--- Installing/updating training deps ---')
child.sendline(
    'pip install -q --upgrade '
    'torch transformers peft trl bitsandbytes datasets accelerate trackio '
    'huggingface_hub 2>&1 | tail -5'
)
wait_prompt(child, 300)  # pip can be slow

# ── Create tmux sessions for training ────────────────────────────────────────
print('\n--- Killing stale tmux sessions ---')
child.sendline('tmux kill-session -t uz-latin 2>/dev/null; tmux kill-session -t uz-cyrillic 2>/dev/null; echo OK')
wait_prompt(child, 10)

# HF_TOKEN
print('\n--- Setting HF_TOKEN ---')
child.sendline('echo "Enter HF_TOKEN:" && read -s HF_TOKEN_VAL && export HF_TOKEN=$HF_TOKEN_VAL')
# We'll set it inline in the tmux commands instead
# Use environment variable if already set on server, else skip trackio
child.sendline('echo $HF_TOKEN | head -c10')
wait_prompt(child, 10)

# Launch Uzbek Latin in tmux (background)
print('\n--- Launching Uzbek LATIN training in tmux: uz-latin ---')
latin_cmd = (
    'cd /root/aziza-build && '
    'python3 train_uzbek_latin_hf.py 2>&1 | tee /root/aziza-build/logs/train_uz_latin.log'
)
child.sendline(f"tmux new-session -d -s uz-latin 'bash -c \"{latin_cmd}\"'")
wait_prompt(child, 15)
child.sendline('tmux ls | grep uz-latin && echo "LATIN_SESSION_OK"')
wait_prompt(child, 10)

# Launch Uzbek Cyrillic in tmux (background)
print('\n--- Launching Uzbek CYRILLIC training in tmux: uz-cyrillic ---')
cyrillic_cmd = (
    'cd /root/aziza-build && '
    'python3 train_uzbek_cyrillic_hf.py 2>&1 | tee /root/aziza-build/logs/train_uz_cyrillic.log'
)
child.sendline(f"tmux new-session -d -s uz-cyrillic 'bash -c \"{cyrillic_cmd}\"'")
wait_prompt(child, 15)
child.sendline('tmux ls | grep uz-cyrillic && echo "CYRILLIC_SESSION_OK"')
wait_prompt(child, 10)

# ── Verify sessions running ──────────────────────────────────────────────────
print('\n--- Active tmux sessions ---')
child.sendline('tmux ls')
wait_prompt(child, 10)

# Show first 20 lines of each log after 10s
print('\n--- Waiting 15s for processes to start ---')
time.sleep(15)

child.sendline('echo "=== LATIN LOG ===" && head -30 /root/aziza-build/logs/train_uz_latin.log 2>/dev/null || echo "log not yet created"')
wait_prompt(child, 15)

child.sendline('echo "=== CYRILLIC LOG ===" && head -30 /root/aziza-build/logs/train_uz_cyrillic.log 2>/dev/null || echo "log not yet created"')
wait_prompt(child, 15)

# ── Restart PM2 services with new code ──────────────────────────────────────
print('\n--- Restarting PM2 services ---')
child.sendline('sudo pm2 restart aziza-gateway aziza-russian-test 2>&1 | tail -5')
i = child.expect(['password for', r'\$', r'#'], timeout=20)
if i == 0:
    child.sendline(PASS)
    wait_prompt(child, 30)

child.sendline('sudo pm2 list')
wait_prompt(child, 15)

ssh_host = os.environ.get("AZIZA_SSH_HOST", "")
print('\n--- Monitoring commands (run in new terminal) ---')
child.sendline(f'echo "Monitor Latin:   ssh aziza@{ssh_host} tmux attach -t uz-latin"')
child.sendline(f'echo "Monitor Cyrillic: ssh aziza@{ssh_host} tmux attach -t uz-cyrillic"')
child.sendline(f'echo "Tail Latin log:  ssh aziza@{ssh_host} tail -f /root/aziza-build/logs/train_uz_latin.log"')
wait_prompt(child, 10)

child.sendline('exit')
child.expect(pexpect.EOF, timeout=15)

print('\n' + '='*60)
print('✅ DEPLOY + TRAINING LAUNCH COMPLETE')
print('='*60)
print(f'Uzbek Latin    → tmux attach -t uz-latin   on {ssh_host}')
print(f'Uzbek Cyrillic → tmux attach -t uz-cyrillic on {ssh_host}')
print('Adapters will push to HuggingFace Hub when done.')
