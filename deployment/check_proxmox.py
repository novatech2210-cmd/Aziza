import os
import pexpect
import sys
import time

proxmox_host = os.environ.get("PROXMOX_HOST", "")
proxmox_pass = os.environ.get("PROXMOX_ROOT_PASS", "")

child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no root@{proxmox_host}', encoding='utf-8', timeout=15)
child.logfile = sys.stdout
idx = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT])
if idx == 0:
    child.sendline(proxmox_pass)
    idx2 = child.expect([r'root@node53:~#', 'Permission denied', pexpect.EOF, pexpect.TIMEOUT])
    if idx2 == 0:
        time.sleep(1)
        child.sendline('qm list')
        child.expect(r'root@node53:~#')
        
        child.sendline('pm2 status')
        child.expect(r'root@node53:~#')
        
        child.sendline('systemctl status moshi vllm aziza-gateway --no-pager')
        child.expect(r'root@node53:~#')
        
        child.sendline('exit')
    else:
        print('Failed to login.')
