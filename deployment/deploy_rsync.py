import os
import pexpect
import sys

REMOTE_HOST = f'aziza@{os.environ.get("AZIZA_SSH_HOST", "")}'
REMOTE_PASSWORD = os.environ.get("AZIZA_SSH_PASS", "")
# Production code lives at /root/aziza-build on the server
REMOTE_BUILD_PATH = '/root/aziza-build/'
LOCAL_BUILD_PATH = '/home/kali/Desktop/AZIZA-BUILD/'

# ── 1. RSYNC ──────────────────────────────────────────────────────────────────
print("=" * 60)
print("STEP 1: Syncing code to /root/aziza-build on remote server")
print("=" * 60)

child = pexpect.spawn(
    f'rsync -avz --exclude ".git" --exclude "__pycache__" '
    f'--exclude "*.pyc" --exclude "node_modules" --exclude "venv" '
    f'--exclude "*.log" '
    f'{LOCAL_BUILD_PATH} {REMOTE_HOST}:{REMOTE_BUILD_PATH}',
    encoding='utf-8'
)
child.logfile = sys.stdout
child.expect('password:')
child.sendline(REMOTE_PASSWORD)
child.expect(pexpect.EOF, timeout=3600)

print("\nRsync completed.\n")

# ── 2. SSH POST-DEPLOY ────────────────────────────────────────────────────────
print("=" * 60)
print("STEP 2: Running post-deploy steps via SSH")
print("=" * 60)

child = pexpect.spawn(
    f'ssh -o StrictHostKeyChecking=no {REMOTE_HOST}',
    encoding='utf-8',
    timeout=60
)
child.logfile = sys.stdout
child.expect('password:')
child.sendline(REMOTE_PASSWORD)
child.expect(r'\$')

# Restart the API gateway to pick up any code changes
print("\n--- Restarting aziza-gateway ---")
child.sendline('sudo pm2 restart aziza-gateway')
i = child.expect(['password for aziza:', r'\$'], timeout=30)
if i == 0:
    child.sendline(REMOTE_PASSWORD)
    child.expect(r'\$', timeout=30)

# Restart the Russian ASR service
print("\n--- Restarting aziza-russian-test ---")
child.sendline('sudo pm2 restart aziza-russian-test')
child.expect(r'\$', timeout=30)

# Show final pm2 status
print("\n--- PM2 Status ---")
child.sendline('sudo pm2 list')
child.expect(r'\$', timeout=30)

# Tail last 10 lines of gateway log to confirm it came up
print("\n--- Gateway logs (last 10 lines) ---")
child.sendline('sudo pm2 logs aziza-gateway --lines 10 --nostream')
child.expect(r'\$', timeout=30)

child.sendline('echo "=== DEPLOY COMPLETE ==="')
child.expect(r'\$', timeout=15)

child.sendline('exit')
child.expect(pexpect.EOF)

print("\n✅ Deployment finished.")
