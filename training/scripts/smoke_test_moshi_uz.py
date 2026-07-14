#!/usr/bin/env python3
"""
Smoke test for Moshi Uzbek LoRA training pipeline.
Runs a minimal training run to verify the pipeline works end-to-end.
"""
import os
import sys
import torch

# Add training scripts to path
sys.path.insert(0, '/root/aziza-build/training/scripts')

# Patch fire import if missing
try:
    import fire
except ImportError:
    import argparse
    class _FireFallback:
        @staticmethod
        def Fire(fn):
            import inspect
            sig = inspect.signature(fn)
            def wrapper():
                args = {}
                for name, param in sig.parameters.items():
                    if name == 'output_dir':
                        args['output_dir'] = '/root/aziza-build/training/lora/adapters/moshi_uz_v1_smoke'
                    elif name == 'resume_from':
                        args['resume_from'] = None
                    elif name == 'data_dir':
                        args['data_dir'] = '/root/aziza-build/training/datasets/uzbek'
                    elif name == 'lang':
                        args['lang'] = 'uz'
                    elif name == 'epochs':
                        args['epochs'] = 0.05
                    else:
                        args[name] = param.default
                return fn(**args)
            return wrapper
    sys.modules['fire'] = _FireFallback()

from finetune_moshi import train

if __name__ == '__main__':
    os.makedirs('/root/aziza-build/training/lora/adapters/moshi_uz_v1_smoke', exist_ok=True)
    train(
        output_dir='/root/aziza-build/training/lora/adapters/moshi_uz_v1_smoke',
        data_dir='/root/aziza-build/training/datasets/uzbek',
        lang='uz',
        epochs=0.05,
    )
