import sys
import os
import torch
sys.path.append("/root/aziza-build/venv/lib/python3.12/site-packages")
from moshi.models import loaders

try:
    print("Loading pkg...")
    pkg = loaders.get_moshi_package("hf://kyutai/moshika-pytorch-bf16")
    print("Pkg loaded:", type(pkg))
    
    mimi = pkg.get_condition_model(condition_id="mimi")
    print("mimi:", type(mimi))
    
    moshi_lm = pkg.get_condition_model(condition_id="moshi_lm")
    print("moshi_lm:", type(moshi_lm))
except Exception as e:
    import traceback
    traceback.print_exc()
