import torch
import traceback
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import os

HF_TOKEN = os.environ.get('HF_TOKEN')
MODEL_ID = 'Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24'
bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16)

try:
    AutoModelForCausalLM.from_pretrained(MODEL_ID, device_map={"model": 0, "lm_head": 0}, quantization_config=bnb_config, token=HF_TOKEN, trust_remote_code=True)
except Exception as e:
    traceback.print_exc()
