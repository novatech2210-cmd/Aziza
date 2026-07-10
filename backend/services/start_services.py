import os
import pexpect
import sys
import time

HOST = os.environ.get("AZIZA_SSH_HOST", "")
USER = 'aziza'
PASS = os.environ.get("AZIZA_SSH_PASS", "")

PROMPT = r'aziza@aziza-worker-01'

def connect():
    child = pexpect.spawn(
        f'ssh -o StrictHostKeyChecking=no -o ConnectTimeout=20 -o ServerAliveInterval=10 {USER}@{HOST}',
        encoding='utf-8', timeout=30
    )
    child.logfile = sys.stdout
    # Could get password prompt OR direct shell if key auth is set up
    idx = child.expect(['password:', 'yes/no', PROMPT, pexpect.EOF, pexpect.TIMEOUT], timeout=25)
    if idx == 1:
        child.sendline('yes')
        idx = child.expect(['password:', PROMPT, pexpect.EOF, pexpect.TIMEOUT], timeout=15)
        if idx == 1:  # direct shell
            child.expect(r'\$\s*$', timeout=10)
            print("\n=== CONNECTED (key auth) ===\n")
            return child
    if idx == 0:
        child.sendline(PASS)
        idx2 = child.expect([PROMPT, 'Permission denied', pexpect.EOF, pexpect.TIMEOUT], timeout=25)
        if idx2 != 0:
            print("LOGIN FAILED:", repr(child.before[-200:]))
            return None
        child.expect(r'\$\s*$', timeout=10)
        print("\n=== CONNECTED (password auth) ===\n")
        return child
    elif idx == 2:
        # Logged in without password (key auth)
        child.expect(r'\$\s*$', timeout=10)
        print("\n=== CONNECTED (key auth, direct) ===\n")
        return child
    else:
        print("FAILED TO CONNECT:", repr(child.before[-200:]))
        return None

def run(child, cmd, timeout=30):
    child.sendline(cmd)
    child.expect([PROMPT + r'.*\$'], timeout=timeout)
    out = child.before.strip()
    print(f"$ {cmd}\n{out}\n")
    return out

child = connect()
if not child:
    sys.exit(1)

# ── Disk & Memory ────────────────────────────────────────────────────────────
run(child, 'df -h /')
run(child, 'free -h')

# ── PostgreSQL ───────────────────────────────────────────────────────────────
print("=== PostgreSQL ===")
run(child, 'systemctl is-active postgresql 2>&1 || true')

child.sendline(f'echo "{PASS}" | sudo -S systemctl enable --now postgresql 2>&1')
child.expect([PROMPT + r'.*\$'], timeout=20)
print(child.before.strip())

run(child, 'systemctl is-active postgresql')

# ── Setup DB user and database ───────────────────────────────────────────────
print("=== DB Init ===")
child.sendline(f"""echo "{PASS}" | sudo -S -u postgres psql -c "SELECT 1 FROM pg_roles WHERE rolname='aziza';" 2>&1""")
child.expect([PROMPT + r'.*\$'], timeout=15)
out = child.before
print(out)

if '(1 row)' not in out:
    child.sendline(f"""echo "{PASS}" | sudo -S -u postgres psql -c "CREATE USER aziza WITH PASSWORD '{PASS}' CREATEDB;" 2>&1""")
    child.expect([PROMPT + r'.*\$'], timeout=15)
    print(child.before.strip())

child.sendline(f"""echo "{PASS}" | sudo -S -u postgres psql -c "SELECT 1 FROM pg_database WHERE datname='aziza_db';" 2>&1""")
child.expect([PROMPT + r'.*\$'], timeout=15)
out = child.before
print(out)

if '(1 row)' not in out:
    child.sendline(f"""echo "{PASS}" | sudo -S -u postgres psql -c "CREATE DATABASE aziza_db OWNER aziza;" 2>&1""")
    child.expect([PROMPT + r'.*\$'], timeout=15)
    print(child.before.strip())

run(child, f'echo "{PASS}" | sudo -S -u postgres psql -l 2>&1 | grep aziza')

# ── Redis ────────────────────────────────────────────────────────────────────
print("=== Redis ===")
child.sendline(f'echo "{PASS}" | sudo -S systemctl enable --now redis-server 2>&1 || echo redis-failed')
child.expect([PROMPT + r'.*\$'], timeout=15)
print(child.before.strip())
run(child, 'systemctl is-active redis-server 2>/dev/null || echo not-running')

# ── Nginx ────────────────────────────────────────────────────────────────────
print("=== Nginx ===")
child.sendline(f'echo "{PASS}" | sudo -S systemctl enable --now nginx 2>&1 || echo nginx-failed')
child.expect([PROMPT + r'.*\$'], timeout=15)
print(child.before.strip())
run(child, 'systemctl is-active nginx || echo not-running')

# ── Check sync dir ────────────────────────────────────────────────────────────
print("=== AZIZA-BUILD-SYNC ===")
out = run(child, 'ls ~/AZIZA-BUILD-SYNC/ 2>/dev/null | head -15 || echo DIR_MISSING')

# ── PM2 ─────────────────────────────────────────────────────────────────────
print("=== PM2 ===")
run(child, 'pm2 list 2>/dev/null || echo pm2-not-found', timeout=15)

eco_check = run(child, 'test -f ~/AZIZA-BUILD-SYNC/ecosystem.config.js && echo EXISTS || echo MISSING')

if 'EXISTS' in eco_check:
    child.sendline('cd ~/AZIZA-BUILD-SYNC && pm2 start ecosystem.config.js --update-env 2>&1 | tail -15')
    child.expect([PROMPT + r'.*\$'], timeout=120)
    print(child.before.strip())
    run(child, 'pm2 save', timeout=10)
    run(child, 'pm2 list', timeout=10)
else:
    print("ecosystem.config.js not found in AZIZA-BUILD-SYNC - skipping PM2 start")
    run(child, 'ls ~ | grep -i aziza')

# ── Final status ─────────────────────────────────────────────────────────────
print("=== FINAL STATUS ===")
run(child, 'df -h /')
run(child, 'systemctl is-active postgresql redis-server nginx 2>&1')

print("\n=== ALL DONE ===")
child.sendline('exit')
