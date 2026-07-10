import sys

filepath = '/root/aziza-build/venv312/lib/python3.12/site-packages/trl/trainer/sft_trainer.py'
with open(filepath, 'r') as f:
    content = f.read()

target = "if isinstance(lm_head_weight, torch.distributed.tensor.DTensor):"
replacement = "if hasattr(torch.distributed, 'tensor') and hasattr(torch.distributed.tensor, 'DTensor') and isinstance(lm_head_weight, torch.distributed.tensor.DTensor):"

if target in content:
    content = content.replace(target, replacement)
    with open(filepath, 'w') as f:
        f.write(content)
    print("Successfully patched trl/trainer/sft_trainer.py")
else:
    print("Target string not found. File might already be patched or different.")
