import os
import re

def fix_ecosystem(base_dir):
    pm2_path = os.path.join(base_dir, 'configs', 'pm2', 'ecosystem.config.js')
    if os.path.exists(pm2_path):
        with open(pm2_path, 'r') as f:
            content = f.read()
        
        # ensure PYTHONPATH for aziza-russian-test
        if 'PYTHONPATH' not in content.split('name: "aziza-russian-test"')[1]:
            content = content.replace(
                'env: {\n        PORT: 8020',
                'env: {\n        PYTHONPATH: "/root/aziza-build",\n        PORT: 8020'
            )
        
        with open(pm2_path, 'w') as f:
            f.write(content)
        print("Updated ecosystem.config.js for PYTHONPATH.")

if __name__ == "__main__":
    fix_ecosystem(".")
