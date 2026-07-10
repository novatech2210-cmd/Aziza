"""
Quick validation: Load Moshi natively, wrap it, apply LoRA, and verify
trainable parameters exist without a ValueError.
Run on the server:
  source venv/bin/activate && python3 /home/pers/validate_lora_init.py
"""
import torch
import torch.nn as nn
from transformers import PreTrainedModel, PretrainedConfig
from transformers.modeling_outputs import CausalLMOutputWithPast
from peft import LoraConfig, TaskType, get_peft_model

# --- Load Moshi natively ---
from huggingface_hub import hf_hub_download
from moshi.models import loaders as moshi_loaders

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[Device] {device}")

moshi_weight_path = hf_hub_download("kyutai/moshika-pytorch-bf16", "model.safetensors")
print(f"[Weights] {moshi_weight_path}")

moshi_lm_raw = moshi_loaders.get_moshi_lm(moshi_weight_path, device=device)
print("[OK] Native Moshi LM loaded")

# --- Wrap in PreTrainedModel shim ---
class _MoshiConfig(PretrainedConfig):
    model_type = "moshi_lm"

class _MoshiWrapper(PreTrainedModel):
    config_class = _MoshiConfig
    supports_gradient_checkpointing = False

    def __init__(self, inner: nn.Module, vocab_size: int = 32768):
        cfg = _MoshiConfig()
        cfg.vocab_size = vocab_size
        super().__init__(cfg)
        self.moshi_lm = inner

    def get_input_embeddings(self):
        # Required by PreTrainedModel; Moshi embeds tokens internally.
        try:
            return self.moshi_lm.emb
        except AttributeError:
            return None

    def prepare_inputs_for_generation(self, input_ids, **kwargs):
        # Stub required by PeftModelForCausalLM init.
        # Actual generation is not used during fine-tuning.
        return {"input_ids": input_ids}

    def forward(self, input_ids, labels=None, attention_mask=None, **kwargs):
        try:
            out = self.moshi_lm(input_ids)
        except Exception:
            out = self.moshi_lm(input_ids, torch.zeros_like(input_ids))

        logits = out if isinstance(out, torch.Tensor) else (out.logits if hasattr(out, "logits") else out[0])
        loss = None
        if labels is not None:
            shift_logits = logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()
            loss = nn.functional.cross_entropy(
                shift_logits.view(-1, shift_logits.size(-1)),
                shift_labels.view(-1), ignore_index=-100
            )
        return CausalLMOutputWithPast(loss=loss, logits=logits)

moshi_lm_raw = moshi_lm_raw.to(torch.bfloat16)
model = _MoshiWrapper(moshi_lm_raw)
model.to(device)
for param in model.parameters():
    param.requires_grad = False
print("[OK] Wrapper created, all params frozen")

# --- Apply LoRA ---
lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    # in_projs / out_projs are ModuleLists: target the indexed Linear children
    target_modules=[
        r"in_projs\.\d+",   # self_attn Q+K+V input projection
        r"out_projs\.\d+",  # self_attn output projection
        "linear_in",         # gating FFN input
        "linear_out",        # gating FFN output
    ],
    bias="none",
    inference_mode=False,
)

try:
    model = get_peft_model(model, lora_config)
    print("[OK] LoRA adapter applied successfully!")
    model.print_trainable_parameters()
except ValueError as e:
    print(f"[FAIL] ValueError: {e}")
    print("\n[Debug] Available nn.Linear modules:")
    for n, m in model.named_modules():
        if isinstance(m, nn.Linear):
            print(f"  {n}")
    raise
