import os
import pexpect
import sys

def run_ssh(host, user, pwd):
    print(f"Connecting to {user}@{host}...")
    child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {user}@{host}', encoding='utf-8', timeout=15)
    child.logfile = sys.stdout
    idx = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT])
    if idx == 0:
        child.sendline(pwd)
        idx2 = child.expect([r'\$', r'#', pexpect.EOF, pexpect.TIMEOUT])
        if idx2 in [0, 1]:
            print("Connected!")
            child.sendline('uptime')
            child.expect([r'\$', r'#'])
            
            child.sendline('nvidia-smi')
            child.expect([r'\$', r'#'])
            
            # if root on proxmox, check qm list
            if user == 'root':
                child.sendline('qm list')
                child.expect([r'\$', r'#'])
                
            child.sendline('exit')
        else:
            print("Failed to get prompt after password")
    else:
        print("Failed to connect or timeout")

print(f"Checking VM ({os.environ.get('AZIZA_SSH_HOST', '')})...")
run_ssh(os.environ.get("AZIZA_SSH_HOST", ""), 'aziza', os.environ.get("AZIZA_SSH_PASS", ""))

print(f"\n\nChecking Proxmox ({os.environ.get('PROXMOX_HOST', '')})...")
run_ssh(os.environ.get("PROXMOX_HOST", ""), 'root', os.environ.get("PROXMOX_SSH_PASS", ""))
