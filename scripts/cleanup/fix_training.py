import os
import pexpect

SSH_HOST = os.environ.get("AZIZA_SSH_HOST", "")
SSH_PASS = os.environ.get("AZIZA_SSH_PASS", "")

with open('output_fix.txt', 'w') as f:
    try:
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o PubkeyAuthentication=no -o PreferredAuthentications=password aziza@{SSH_HOST}', encoding='utf-8', timeout=120)
        child.logfile_read = f
        child.expect('(?i)password:')
        child.sendline(SSH_PASS)
        child.expect(r'\$')
        
        child.sendline('sudo su -')
        child.expect('(?i)password')
        child.sendline(SSH_PASS)
        child.expect('#')
        
        child.sendline('tmux kill-session -t uz-cyrillic')
        child.expect('#')
        child.sendline('tmux kill-session -t uz-latin')
        child.expect('#')
        
        child.sendline('source /root/aziza-build/venv/bin/activate')
        child.expect('#')
        
        child.sendline('pip uninstall -y torch torchvision torchaudio')
        child.expect('#')
        
        child.sendline('pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121')
        child.expect('#')
        
        hf_token = os.environ.get("HF_TOKEN", "")
        if not hf_token:
            raise RuntimeError("HF_TOKEN environment variable not set")
        
        child.sendline(f'tmux new-session -d -s uz-cyrillic "source /root/aziza-build/venv/bin/activate && HF_TOKEN={hf_token} python3 /root/aziza-build/train_uzbek_cyrillic_hf.py > /root/aziza-build/logs/train_uz_cyrillic.log 2>&1"')
        child.expect('#')
        
        child.sendline(f'tmux new-session -d -s uz-latin "source /root/aziza-build/venv/bin/activate && HF_TOKEN={hf_token} python3 /root/aziza-build/train_uzbek_latin_hf.py > /root/aziza-build/logs/train_uz_latin.log 2>&1"')
        child.expect('#')
        
        child.sendline('exit')
    except Exception as e:
        print('Error:', e)
