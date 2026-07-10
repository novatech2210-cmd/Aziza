import os
import pexpect
import sys

proxmox_host = os.environ.get("PROXMOX_HOST", "")
proxmox_pass = os.environ.get("PROXMOX_ROOT_PASS", "")

child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no root@{proxmox_host}', encoding='utf-8', timeout=15)
child.logfile = sys.stdout

idx = child.expect(['assword:', pexpect.EOF, pexpect.TIMEOUT])
if idx == 0:
    child.sendline(proxmox_pass)
    # Use a more specific prompt or wait for #
    idx2 = child.expect([r'root@node53:~#', pexpect.EOF, pexpect.TIMEOUT])
    if idx2 == 0:
        print("\n--- Connected to Proxmox ---")
        child.sendline('qm status 102')
        child.expect(r'root@node53:~#')
        
        child.sendline('qm start 102')
        child.expect(r'root@node53:~#')
        
        child.sendline('qm status 102')
        child.expect(r'root@node53:~#')
        
        child.sendline('exit')
    else:
        print("\nFailed to get prompt after password")
else:
    print("\nFailed to connect or timeout")
