import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import os

HF_TOKEN = os.environ.get("HF_TOKEN", "")
MODEL_ID = "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24"

print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, token=HF_TOKEN, trust_remote_code=True)

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.float16,
)

print("Loading model without device_map...")
try:
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        token=HF_TOKEN,
        trust_remote_code=True,
        quantization_config=bnb_config
    )
    print("Success without device_map! Model device:", model.device)
except Exception as e:
    print("Failed without device_map:", type(e), e)

print("Loading model with device_map='auto'...")
try:
    model2 = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        token=HF_TOKEN,
        trust_remote_code=True,
        quantization_config=bnb_config,
        device_map="auto"
    )
    print("Success with device_map='auto'! Model device:", model2.device)
except Exception as e:
    print("Failed with device_map='auto':", type(e), e)
