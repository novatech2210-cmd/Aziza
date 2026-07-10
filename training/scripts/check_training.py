import os
import pexpect
import sys
import time

HOST = os.environ.get("AZIZA_SSH_HOST", "")
USER = 'aziza'
PASS = os.environ.get("AZIZA_SSH_PASS", "")
PROMPT = r'aziza@aziza-worker-01'

child = pexpect.spawn(
    f'ssh -o StrictHostKeyChecking=no -o ConnectTimeout=20 {USER}@{HOST}',
    encoding='utf-8', timeout=30
)

idx = child.expect(['password:', PROMPT, 'yes/no', pexpect.EOF, pexpect.TIMEOUT], timeout=25)
if idx == 2:
    child.sendline('yes')
    idx = child.expect(['password:', PROMPT, pexpect.EOF, pexpect.TIMEOUT], timeout=15)
if idx == 0:
    child.sendline(PASS)
    child.expect(PROMPT, timeout=20)

child.expect(r'\$', timeout=10)
child.logfile = sys.stdout
time.sleep(0.5)

def run(child, cmd, timeout=20):
    child.sendline(cmd)
    child.expect(PROMPT, timeout=timeout)
    child.expect(r'\$', timeout=5)

print("\n=== GPU STATUS ===")
run(child, 'nvidia-smi 2>/dev/null || echo NO_GPU')

print("\n=== GPU COMPUTE APPS ===")
run(child, 'nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null || echo no-gpu-processes')

print("\n=== RUNNING TRAINING PROCESSES ===")
run(child, 'ps aux | grep -E "(train|finetune|python.*train)" | grep -v grep | head -20')

print("\n=== PM2 LIST (restart counts) ===")
run(child, 'pm2 list')

print("\n=== MOSHI-WORKER LOGS (last 40 lines) ===")
run(child, 'pm2 logs moshi-worker --lines 40 --nostream 2>/dev/null | tail -40 || echo no-logs', timeout=20)

print("\n=== AZIZA-MULTILINGUAL LOGS (last 40 lines) ===")
run(child, 'pm2 logs aziza-multilingual --lines 40 --nostream 2>/dev/null | tail -40 || echo no-logs', timeout=20)

print("\n=== ORCHESTRATOR LOGS (last 20 lines) ===")
run(child, 'pm2 logs orchestrator --lines 20 --nostream 2>/dev/null | tail -20 || echo no-logs', timeout=20)

print("\n=== TRAINING LOG FILES ===")
run(child, 'ls -lh ~/create_model.log ~/install.log ~/aziza-build/*.log 2>/dev/null || echo no-training-logs')

print("\n=== create_model.log (last 60 lines) ===")
run(child, 'tail -60 ~/create_model.log 2>/dev/null || echo file-not-found', timeout=15)

print("\n=== AZIZA-BUILD TRAIN LOGS ===")
run(child, 'ls -lh ~/aziza-build/*.log 2>/dev/null && tail -30 ~/aziza-build/*.log 2>/dev/null | head -60 || echo no-build-logs')

print("\n=== DISK USAGE ===")
run(child, 'df -h /')

print("\n=== MODEL FILES (adapter dirs) ===")
run(child, 'du -sh ~/AZIZA-BUILD-SYNC/adapters/*/ 2>/dev/null | head -10 || echo no-adapter-dirs')

print("\n=== DONE ===")
child.sendline('exit')
