import os
import re

def fix_python_imports(base_dir):
    print("Fixing Python imports...")
    import_replacements = [
        (r'from services(\.|\s+import)', r'from backend.services\1'),
        (r'import services(\.|\n)', r'import backend.services\1'),
        (r'from workers(\.|\s+import)', r'from backend.workers\1'),
        (r'import workers(\.|\n)', r'import backend.workers\1'),
        (r'from gateway(\.|\s+import)', r'from backend.gateway\1'),
        (r'import gateway(\.|\n)', r'import backend.gateway\1'),
        (r'from api(\.|\s+import)', r'from backend.api\1'),
        (r'import api(\.|\n)', r'import backend.api\1'),
    ]

    for root, dirs, files in os.walk(base_dir):
        if 'node_modules' in root or 'venv' in root or '__pycache__' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r') as f:
                        content = f.read()
                    
                    new_content = content
                    for old, new in import_replacements:
                        new_content = re.sub(old, new, new_content)
                    
                    if new_content != content:
                        with open(filepath, 'w') as f:
                            f.write(new_content)
                        print(f"Updated imports in {filepath}")
                except Exception as e:
                    print(f"Failed to process {filepath}: {e}")

def fix_shell_scripts(base_dir):
    print("Fixing shell scripts...")
    path_replacements = [
        (r'adapters/', r'training/lora/'),
        (r'datasets/', r'training/datasets/'),
        (r'configs/', r'configs/pm2/'), # Be careful with this one
    ]
    # More precise replacements
    for root, dirs, files in os.walk(base_dir):
        if 'node_modules' in root or 'venv' in root:
            continue
        for file in files:
            if file.endswith('.sh') or file.endswith('.exp'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r') as f:
                        content = f.read()
                    
                    new_content = content
                    new_content = new_content.replace('adapters/', 'training/lora/')
                    new_content = new_content.replace('fine-tuning/adapters/', 'training/lora/')
                    new_content = new_content.replace('--lora_modules adapters/', '--lora_modules training/lora/')
                    new_content = new_content.replace('pm2 start ecosystem.config.js', 'pm2 start configs/pm2/ecosystem.config.js')
                    new_content = new_content.replace('nginx/aziza.conf', 'configs/nginx/aziza.conf')
                    
                    if new_content != content:
                        with open(filepath, 'w') as f:
                            f.write(new_content)
                        print(f"Updated paths in {filepath}")
                except Exception as e:
                    pass

def fix_configs(base_dir):
    print("Fixing configs...")
    # PM2
    pm2_path = os.path.join(base_dir, 'configs', 'pm2', 'ecosystem.config.js')
    if os.path.exists(pm2_path):
        with open(pm2_path, 'r') as f:
            content = f.read()
        
        # Replace root paths with new paths
        new_content = content.replace('script: "gateway/server.js"', 'script: "backend/gateway/server.js"')
        new_content = new_content.replace('script: "services/', 'script: "backend/services/')
        new_content = new_content.replace('script: "api/', 'script: "backend/api/')
        new_content = new_content.replace('script: "workers/', 'script: "backend/workers/')
        new_content = new_content.replace('cwd: "frontend"', 'cwd: "frontend/web"')
        
        if new_content != content:
            with open(pm2_path, 'w') as f:
                f.write(new_content)
            print(f"Updated PM2 config {pm2_path}")

    # NGINX
    nginx_path = os.path.join(base_dir, 'configs', 'nginx', 'aziza.conf')
    if os.path.exists(nginx_path):
        with open(nginx_path, 'r') as f:
            content = f.read()
        
        new_content = content.replace('root /root/aziza-build/frontend/dist;', 'root /root/aziza-build/frontend/web/dist;')
        new_content = new_content.replace('root /var/www/aziza/frontend/dist;', 'root /root/aziza-build/frontend/web/dist;')
        
        if new_content != content:
            with open(nginx_path, 'w') as f:
                f.write(new_content)
            print(f"Updated Nginx config {nginx_path}")

def generate_docs(base_dir):
    print("Generating docs...")
    eng_dir = os.path.join(base_dir, 'engineering')
    os.makedirs(eng_dir, exist_ok=True)
    
    with open(os.path.join(eng_dir, 'STARTUP.md'), 'w') as f:
        f.write("# AZIZA Startup Sequence\n\n")
        f.write("1. Redis & MongoDB\n2. vLLM instances\n3. Gateway\n4. Frontend\n")
    
    with open(os.path.join(eng_dir, 'IMPORT_GRAPH.md'), 'w') as f:
        f.write("# Import Graph\n\n- `backend/` serves as the root module for all internal APIs.\n- Example: `from backend.services.gpu import ...`\n")

if __name__ == "__main__":
    base = "."
    fix_python_imports(base)
    fix_shell_scripts(base)
    fix_configs(base)
    generate_docs(base)
    print("Stabilization script completed.")
