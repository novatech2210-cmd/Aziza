import os
import re

file_path = '/root/aziza-build/venv312/lib/python3.12/site-packages/transformers/integrations/bitsandbytes.py'
with open(file_path, 'r') as f:
    content = f.read()

replacement = '''
                    new_module.requires_grad_(False)
                    parent = model
                    atoms = module_name.split('.')
                    for atom in atoms[:-1]:
                        parent = getattr(parent, atom)
                    setattr(parent, atoms[-1], new_module)
                    has_been_replaced = True
'''
content = re.sub(
    r'                    new_module\.requires_grad_\(False\)\n                    model\.set_submodule\(module_name, new_module\)\n                    has_been_replaced = True',
    replacement.strip('\n'),
    content
)

with open(file_path, 'w') as f:
    f.write(content)

print('Transformers bitsandbytes integration patched successfully.')
