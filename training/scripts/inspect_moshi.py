import torch
from huggingface_hub import hf_hub_download
from moshi.models import loaders

device = 'cpu'
moshi_path = hf_hub_download('kyutai/moshiko-pytorch-bf16', 'model.safetensors', local_files_only=True)
moshi_lm = loaders.get_moshi_lm(moshi_path, device=device)

print('--- Model Modules ---')
for name, module in moshi_lm.named_modules():
    if isinstance(module, torch.nn.Linear):
        print(f'Linear: {name}')
    elif 'proj' in name.lower() or 'attn' in name.lower() or 'linear' in name.lower():
        print(f'Other: {name} ({type(module)})')

print('--- Keys sample ---')
keys = list(dict(moshi_lm.named_parameters()).keys())
for k in keys[:50]:
    print(k)
