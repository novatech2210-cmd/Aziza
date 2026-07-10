import os
import re

def fix_ecosystem(base_dir):
    print("Fixing ecosystem.config.js")
    pm2_path = os.path.join(base_dir, 'configs', 'pm2', 'ecosystem.config.js')
    if os.path.exists(pm2_path):
        with open(pm2_path, 'r') as f:
            content = f.read()
        
        # We need to change:
        # /root/aziza-build/adapters/ru_all -> /root/aziza-build/training/lora/adapters/ru_all
        # /root/aziza-build/adapters/aziza-adapter-final-uz -> /root/aziza-build/training/lora/adapters/aziza-adapter-final-uz
        # /root/aziza-build/en_chatml.jinja -> /root/aziza-build/training/scripts/en_chatml.jinja
        # cwd: "/root/aziza-build", args: "-m uvicorn serve_russian_test:app ... " -> cwd: "/root/aziza-build/backend/gateway"
        
        new_content = content.replace('/root/aziza-build/adapters/', '/root/aziza-build/training/lora/adapters/')
        new_content = new_content.replace('/root/aziza-build/en_chatml.jinja', '/root/aziza-build/training/scripts/en_chatml.jinja')
        
        # update cwd for aziza-russian-test
        new_content = new_content.replace(
            'cwd: "/root/aziza-build",\n      env: {\n        PORT: 8020',
            'cwd: "/root/aziza-build/backend/gateway",\n      env: {\n        PORT: 8020'
        )

        # Let's ensure orchestrator and vllm apps use absolute paths if they broke. 
        # vllm instances execute from /root/aziza-build, which is fine since they load models.
        
        if new_content != content:
            with open(pm2_path, 'w') as f:
                f.write(new_content)
            print("ecosystem.config.js updated successfully.")
        else:
            print("No changes needed in ecosystem.config.js.")

def fix_nginx(base_dir):
    print("Fixing nginx config")
    nginx_path = os.path.join(base_dir, 'configs', 'nginx', 'nginx', 'aziza.conf')
    if not os.path.exists(nginx_path):
        nginx_path = os.path.join(base_dir, 'configs', 'nginx', 'aziza.conf')
        
    if os.path.exists(nginx_path):
        with open(nginx_path, 'r') as f:
            content = f.read()
            
        new_content = content.replace('root /root/aziza-build/frontend/dist;', 'root /root/aziza-build/frontend/web/dist;')
        
        # The api proxy was likely pointing to localhost:8080 or similar, which is fine.
        if new_content != content:
            with open(nginx_path, 'w') as f:
                f.write(new_content)
            print(f"Updated Nginx config {nginx_path}")
        else:
            print("No changes needed in nginx.")

if __name__ == "__main__":
    base = "."
    fix_ecosystem(base)
    fix_nginx(base)
