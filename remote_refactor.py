import os
import shutil
import re
from pathlib import Path

# Target directories
BASE_DIR = Path.cwd()
TARGET_DIRS = {
    'backend': ['api', 'services', 'workers', 'gateway'],
    'frontend': ['web', 'chat', 'admin'],
    'training': ['datasets', 'lora', 'evaluation', 'scripts', 'reports'],
    'deployment': ['vast', 'server', 'cloudflare', 'ssh', 'proxmox'],
    'scripts': ['cleanup', 'maintenance', 'utilities', 'downloads'],
    'configs': ['pm2', 'nginx', 'docker', 'vllm', 'ollama'],
    'engineering': [],
    'docs': ['reports', 'pdf', 'architecture', 'api', 'training'],
    'archive': ['backups', 'logs', 'old-training', 'old-configs', 'review'],
    'logs': [],
    'tmp': [],
    'benchmarks': []
}

def setup_directories():
    for main_dir, subdirs in TARGET_DIRS.items():
        (BASE_DIR / main_dir).mkdir(exist_ok=True)
        for subdir in subdirs:
            (BASE_DIR / main_dir / subdir).mkdir(exist_ok=True, parents=True)

def move_file(src_path, target_dir):
    if not src_path.exists():
        return False
    dst_path = BASE_DIR / target_dir / src_path.name
    if dst_path.exists():
        # Avoid overwrite
        return False
    shutil.move(str(src_path), str(dst_path))
    return True

def generate_engineering_files():
    eng_dir = BASE_DIR / 'engineering'
    files = ['PROJECT.md', 'ARCHITECTURE.md', 'ROADMAP.md', 'BACKLOG.md', 'CURRENT_TASK.md', 'NEXT_TASK.md', 'DECISIONS.md', 'KNOWN_ISSUES.md', 'SESSION.md']
    for f in files:
        f_path = eng_dir / f
        if not f_path.exists():
            f_path.write_text(f"# {f.replace('.md', '')}\nGenerated as part of repository refactoring.\n")

def get_target_dir(filename, is_dir=False):
    name = filename.lower()
    
    # Logs
    if name.endswith('.log') or name.endswith('.pid') or 'log' in name:
        if name.startswith('output_logs') or name.startswith('train_run'):
            return 'archive/logs'
        return 'logs'
    
    # Archive/Tmp
    if name.endswith('.bak') or name.endswith('.bak2') or name.endswith('.bak3') or name.endswith('.backup') or name.startswith('discarded') or name.startswith('old'):
        return 'archive/backups'
    if name.startswith('tmp'):
        return 'tmp'
    
    # Docs
    if name.endswith('.pdf'):
        return 'docs/pdf'
    if name.endswith('.md') or name.endswith('.docx'):
        if 'report' in name:
            return 'docs/reports'
        if name in ['project.md', 'architecture.md', 'roadmap.md', 'backlog.md', 'current_task.md', 'next_task.md', 'decisions.md', 'known_issues.md', 'session.md']:
            return 'engineering'
        if name in ['readme.md']:
            return '.' # Keep root readme
        return 'docs'
        
    # Configs
    if name.endswith('.js') and 'config' in name:
        if 'vllm' in name: return 'configs/vllm'
        return 'configs/pm2'
    if name.endswith('.yaml') or name.endswith('.yml') or 'docker' in name:
        return 'configs/docker'
    if name.startswith('modelfile'):
        return 'configs/ollama'
        
    # Deployment
    if 'deploy' in name or name.endswith('.exp') or 'ssh' in name or 'proxmox' in name or 'cloudflare' in name or 'vm' in name or 'vast' in name:
        return 'deployment'
        
    # Scripts
    if name.startswith('download'):
        return 'scripts/downloads'
    if name.startswith('cleanup') or name.startswith('fix'):
        return 'scripts/cleanup'
    if name.endswith('.sh') and 'start' not in name:
        return 'scripts/utilities'
        
    # Training
    if 'train' in name or 'eval' in name or 'finetune' in name or 'benchmark' in name or 'lora' in name or 'dataset' in name or name.endswith('.jsonl') or 'moshi' in name or 'adapter' in name or 'chatml' in name:
        if 'eval' in name or 'benchmark' in name:
            return 'training/evaluation'
        if 'dataset' in name or name.endswith('.jsonl'):
            return 'training/datasets'
        return 'training/scripts'
        
    # Frontend
    if 'frontend' in name or name.endswith('.jsx') or name.endswith('.tsx') or name.endswith('.html'):
        return 'frontend'
        
    # Backend
    if name.endswith('.py') or name == 'requirements.txt':
        if 'serve' in name or 'engine' in name or 'gateway' in name or 'proxy' in name:
            return 'backend/gateway'
        return 'backend/services'
        
    return 'archive/review'

def refactor():
    setup_directories()
    generate_engineering_files()
    
    moved_files = []
    review_files = []
    
    # Process files
    for path in list(BASE_DIR.iterdir()):
        if path.is_dir():
            if path.name in TARGET_DIRS or path.name.startswith('.') or path.name in ['venv312', '__pycache__', 'node_modules', 'model_cache', 'benchmarks', 'benchmark']:
                continue
            # Directory routing
            if path.name == 'nginx': target = 'configs/nginx'
            elif path.name == 'fine-tuning': target = 'training/scripts'
            elif path.name == 'frontend': target = 'frontend/web'
            elif path.name == 'reports': target = 'docs/reports'
            elif 'adapter' in path.name.lower(): target = 'training/lora'
            else: target = 'archive/review'
            
            if target.split('/')[0] != path.name:
                if move_file(path, target):
                    moved_files.append((path.name, target))
                    if target == 'archive/review':
                        review_files.append(path.name)
        else:
            if path.name in ['remote_refactor.py']: continue
            target = get_target_dir(path.name)
            if target == '.': continue
            
            if move_file(path, target):
                moved_files.append((path.name, target))
                if target == 'archive/review':
                    review_files.append(path.name)
                    
    # Generate Reports
    reports_dir = BASE_DIR / 'engineering'
    
    with open(reports_dir / 'FILE_MOVE_REPORT.md', 'w') as f:
        f.write("# File Move Report\n\n")
        for src, dst in moved_files:
            f.write(f"- `{src}` -> `{dst}/`\n")
            
    with open(reports_dir / 'MANUAL_REVIEW.md', 'w') as f:
        f.write("# Required Manual Review Items\n\n")
        f.write("The following items were placed in `archive/review/` due to uncertain ownership:\n\n")
        for item in review_files:
            f.write(f"- `{item}`\n")
            
    with open(reports_dir / 'GITIGNORE_SUGGESTIONS.md', 'w') as f:
        f.write("# Suggested .gitignore Improvements\n\n```\nlogs/\ntmp/\narchive/\nmodel_cache/\nvenv312/\n__pycache__/\n```\n")
        
    os.system("tree -L 3 > engineering/REPO_TREE.md")

if __name__ == '__main__':
    refactor()
