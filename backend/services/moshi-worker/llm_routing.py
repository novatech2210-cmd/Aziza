"""
LLM Routing -- language-based request routing to vLLM endpoints.

Routing strategy:
  English (en): port 8002, Vikhr-Llama3.1-8B base model
  Russian (ru): port 8002, Vikhr-Llama3.1-8B base model (NOT aziza_russian LoRA)
    The aziza_russian LoRA has a tokenizer compatibility issue.
    vLLM fails HTTP 400 when LoRA name is passed as model parameter.
    Route through base model with Russian system prompt for language steering.
  Uzbek (uz): port 8003, alloma-3B base model with aziza_uzbek LoRA
"""

from config import LLM_URL_EN, LLM_URL_UZ, LLM_MODEL_EN, LLM_MODEL_UZ, SYSTEM_PROMPTS, SYSTEM_PROMPTS_RAG

# Model name constants
LLM_MODEL_EN_BASE = "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24"
LLM_MODEL_UZ_BASE = "alloma"

# vLLM endpoint ports
VLLM_PORT_EN = 8002
VLLM_PORT_UZ = 8003


def get_system_prompt(language: str) -> str:
    return SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["en"])


def get_rag_prompt(language: str) -> str:
    return SYSTEM_PROMPTS_RAG.get(language, SYSTEM_PROMPTS_RAG["en"])


def get_llm_config(language: str) -> tuple[str, str]:
    """Route to the correct LLM based on language. Returns (url, model_name)."""
    if "uz" in language:
        return LLM_URL_UZ, LLM_MODEL_UZ_BASE
    if "ru" in language:
        return LLM_URL_EN, LLM_MODEL_EN_BASE
    return LLM_URL_EN, LLM_MODEL_EN_BASE


def get_request_params(language: str) -> dict:
    """Return language-specific request parameters for vLLM.

    Uzbek (alloma/Qwen-based) uses different stop tokens than
    Vikhr/Llama3-based models. Sending Llama3 stop_token_ids to
    alloma causes HTTP 400/422 because those IDs do not exist in
    the Qwen vocabulary.
    """
    if "uz" in language:
        return {
            "temperature": 0.7,
            "max_tokens": 256,
            "stop": ["<|im_end|>", "<|im_start|>"],
        }
    # English and Russian use Vikhr-Llama3 base model
    return {
        "temperature": 0.6,
        "top_p": 0.9,
        "repetition_penalty": 1.1,
        "presence_penalty": 0.3,
        "max_tokens": 256,
        "stop_token_ids": [128001, 128009],
        "stop": ["<|im_end|>", "<|im_start|>", "<|eot_id|>", "<|end_of_text|>"],
    }
