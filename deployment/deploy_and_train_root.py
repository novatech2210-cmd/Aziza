#!/usr/bin/env python3
"""
deploy_and_train_root.py — Deploy to server as root and launch Uzbek training.
Uses root user via AZIZA_SSH_HOST env var.
"""
import os
import pexpect
import sys
import time

HOST = f'root@{os.environ.get("AZIZA_SSH_HOST", "")}'
PASS = os.environ.get("AZIZA_SSH_PASS", "")
LOCAL = '/home/kali/Desktop/AZIZA-BUILD/'
REMOTE = '/root/aziza-build/'
SSH_OPTS = '-o StrictHostKeyChecking=no -o ConnectTimeout=20 -o ServerAliveInterval=60'

def log(msg):
    print(f'\n{"="*60}\n{msg}\n{"="*60}')

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — rsync as root
# ─────────────────────────────────────────────────────────────────────────────
log('STEP 1: rsync → /root/aziza-build/')

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

idx = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=30)
if idx == 0:
    child.sendline(PASS)
    child.expect(pexpect.EOF, timeout=3600)

print('\n✅ Rsync complete.\n')

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — SSH as root and set everything up
# ─────────────────────────────────────────────────────────────────────────────
log('STEP 2: SSH into server as root')

ssh = pexpect.spawn(
    f'ssh {SSH_OPTS} {HOST}',
    encoding='utf-8',
    timeout=120,
)
ssh.logfile = sys.stdout

def wait(patterns=None, timeout=30):
    if patterns is None:
        patterns = [r'#\s*$', r'\$\s*$']
    return ssh.expect(patterns + [pexpect.TIMEOUT], timeout=timeout)

# Authenticate
idx = ssh.expect(['password:', r'#', r'Last login', pexpect.TIMEOUT], timeout=20)
if idx == 0:
    ssh.sendline(PASS)
    wait(timeout=30)
elif idx == 2:  # Last login banner
    wait(timeout=30)

# ── GPU check ────────────────────────────────────────────────────────────────
ssh.sendline('nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader')
wait(timeout=20)

# ── Make logs dir ─────────────────────────────────────────────────────────────
ssh.sendline('mkdir -p /root/aziza-build/logs && echo LOGS_DIR_OK')
wait(timeout=10)

# ── Python + pip check ───────────────────────────────────────────────────────
ssh.sendline('python3 --version && pip3 --version')
wait(timeout=15)

ssh.sendline('python3 -c "import torch; print(\'torch:\', torch.__version__, \'cuda:\', torch.cuda.is_available())" 2>&1')
wait(timeout=30)

# ── Install / upgrade training deps ──────────────────────────────────────────
log('STEP 3: Installing training dependencies')
ssh.sendline(
    'pip3 install -q --upgrade --break-system-packages '
    'torch transformers peft trl bitsandbytes datasets accelerate '
    'trackio huggingface_hub 2>&1 | tail -8'
)
wait(timeout=600)  # pip can be slow with CUDA packages

# ── Check HF_TOKEN on server ─────────────────────────────────────────────────
ssh.sendline('echo "HF_TOKEN_START:$(echo $HF_TOKEN | head -c15):END" 2>/dev/null')
wait(timeout=10)

# ── Kill any stale training sessions ─────────────────────────────────────────
log('STEP 4: Resetting tmux sessions')
ssh.sendline('tmux kill-session -t uz-latin 2>/dev/null; tmux kill-session -t uz-cyrillic 2>/dev/null; echo SESSIONS_CLEARED')
wait(timeout=10)

# ── Launch Uzbek Latin training ───────────────────────────────────────────────
log('STEP 5: Launch uz-latin training in tmux')
latin_script = '/root/aziza-build/train_uzbek_latin_hf.py'
latin_log    = '/root/aziza-build/logs/train_uz_latin.log'
latin_cmd    = f'cd /root/aziza-build && python3 {latin_script} 2>&1 | tee {latin_log}'

ssh.sendline(f"""tmux new-session -d -s uz-latin bash -c '{latin_cmd}' && echo LATIN_LAUNCHED""")
wait(timeout=20)

# ── Launch Uzbek Cyrillic training ────────────────────────────────────────────
log('STEP 6: Launch uz-cyrillic training in tmux')
cyrillic_script = '/root/aziza-build/train_uzbek_cyrillic_hf.py'
cyrillic_log    = '/root/aziza-build/logs/train_uz_cyrillic.log'
cyrillic_cmd    = f'cd /root/aziza-build && python3 {cyrillic_script} 2>&1 | tee {cyrillic_log}'

ssh.sendline(f"""tmux new-session -d -s uz-cyrillic bash -c '{cyrillic_cmd}' && echo CYRILLIC_LAUNCHED""")
wait(timeout=20)

# ── Verify sessions ───────────────────────────────────────────────────────────
ssh.sendline('tmux ls && echo ALL_SESSIONS_UP')
wait(timeout=10)

# Wait 20s and check logs
print('\nWaiting 20 seconds for scripts to start...')
time.sleep(20)

ssh.sendline(f'echo "=== LATIN LOG (first 40 lines) ===" && head -40 {latin_log} 2>/dev/null || echo "No log yet"')
wait(timeout=15)

ssh.sendline(f'echo "=== CYRILLIC LOG (first 40 lines) ===" && head -40 {cyrillic_log} 2>/dev/null || echo "No log yet"')
wait(timeout=15)

# ── PM2 services ─────────────────────────────────────────────────────────────
log('STEP 7: Restarting PM2 services')
ssh.sendline('pm2 restart all 2>&1 | tail -10 || echo "PM2 restart attempted"')
wait(timeout=30)

ssh.sendline('pm2 list')
wait(timeout=15)

# ── Final summary ─────────────────────────────────────────────────────────────
ssh.sendline('echo "=== DISK ===" && df -h / && echo "=== GPU MEM ===" && nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader')
wait(timeout=20)

ssh.sendline('exit')
ssh.expect(pexpect.EOF, timeout=15)

log('✅ DEPLOY + TRAINING LAUNCH COMPLETE')
ssh_host = os.environ.get("AZIZA_SSH_HOST", "")
print(f"""
Monitor sessions on server:
  ssh root@{ssh_host}
  tmux attach -t uz-latin        # Uzbek Latin training
  tmux attach -t uz-cyrillic     # Uzbek Cyrillic training

Tail logs:
  tail -f /root/aziza-build/logs/train_uz_latin.log
  tail -f /root/aziza-build/logs/train_uz_cyrillic.log

Adapters push to HuggingFace Hub on each checkpoint save.
""")
