import os

VLLM_DTYPE = os.getenv("VLLM_DTYPE", "bfloat16")
VLLM_GPU_MEMORY_UTIL = float(os.getenv("VLLM_GPU_MEMORY_UTIL", "0.45"))
VLLM_MAX_NUM_SEQS = int(os.getenv("VLLM_MAX_NUM_SEQS", "16"))
VLLM_MAX_MODEL_LEN = int(os.getenv("VLLM_MAX_MODEL_LEN", "4096"))
LAUNCH_VLLM = os.getenv("LAUNCH_VLLM", "false").lower() == "true"

LLM_PORT_EN = int(os.getenv("LLM_PORT_EN", "8002"))
LLM_PORT_UZ = int(os.getenv("LLM_PORT_UZ", "8003"))
LLM_GPU_EN = os.getenv("LLM_GPU_EN", "0")
LLM_GPU_UZ = os.getenv("LLM_GPU_UZ", "0")

LLM_URL_EN = os.getenv("TEXT_API_URL", f"http://localhost:{LLM_PORT_EN}/v1/chat/completions")
LLM_URL_UZ = os.getenv("TEXT_API_URL_UZ", f"http://localhost:{LLM_PORT_UZ}/v1/chat/completions")

LLM_MODEL_EN = "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24"
LLM_MODEL_UZ = "uzlm/alloma-3B-Instruct"

SYSTEM_PROMPTS = {
    "ru": (
        "Ты Азиза — тёплый, умный и внимательный AI-ассистент. "
        "Говори естественно по-русски, как живой человек. "
        "Избегай формальных оборотов. Отвечай кратко и по делу."
    ),
    "uz-latn": (
        "Siz Aziza — mehribon, aqlli va diqqatli AI yordamchisiz. "
        "O'zbek tilida tabiiy va jonli gapiring. "
        "Qisqa va aniq javob bering."
    ),
    "uz-cyrl": (
        "Сиз Азиза — меҳрибон, ақлли ва диққатли AI ёрдамчисисиз. "
        "Ўзбек тилида табиий ва жонли гапиринг. "
        "Қисқа ва аниқ жавоб беринг."
    ),
    "uz": (
        "Siz Aziza — mehribon, aqlli va diqqatli AI yordamchisiz. "
        "O'zbek tilida tabiiy va jonli gapiring. "
        "Qisqa va aniq javob bering."
    ),
    "en": (
        "You are Aziza — a warm, intelligent, and attentive AI assistant. "
        "Speak naturally and conversationally. Keep responses concise."
    ),
}

SYSTEM_PROMPTS_RAG = SYSTEM_PROMPTS.copy()
