"""
Qube Backend — LLM Routing & Streaming Service
"""

from config import LLM_URL_EN, LLM_URL_UZ, LLM_MODEL_EN, LLM_MODEL_UZ, SYSTEM_PROMPTS, SYSTEM_PROMPTS_RAG

# The LoRA adapter aliases registered with vLLM
# NOTE: aziza_russian has a tokenizer compatibility issue — use base model instead
LLM_MODEL_EN_BASE = "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24"
LLM_MODEL_RU_LORA = "aziza_russian"   # Only works if tokenizer loads correctly
LLM_MODEL_UZ_LORA = "aziza_uzbek"     # LoRA alias for Uzbek
LLM_MODEL_UZ_BASE = "alloma"          # Base alloma model name


def get_system_prompt(language: str) -> str:
    return SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["en"])


def get_rag_prompt(language: str) -> str:
    return SYSTEM_PROMPTS_RAG.get(language, SYSTEM_PROMPTS_RAG["en"])


def get_llm_config(language: str) -> tuple[str, str]:
    """Route to the correct LLM based on language. Returns (url, model_name)."""
    if "uz" in language:
        # Use base alloma model — aziza_uzbek LoRA is loaded as an adapter
        return LLM_URL_UZ, LLM_MODEL_UZ_BASE
    if "ru" in language:
        # Use base Vikhr model — aziza_russian LoRA tokenizer has a compatibility issue
        # The Russian system prompt steers the response language
        return LLM_URL_EN, LLM_MODEL_EN_BASE
    return LLM_URL_EN, LLM_MODEL_EN_BASE
