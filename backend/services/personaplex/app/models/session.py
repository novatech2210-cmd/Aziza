from pydantic import BaseModel
from typing import Optional

class PersonaSession(BaseModel):
    session_id: str
    user_id: str
    persona_id: str           # "aziza_ru" | "aziza_uz_latn" | "aziza_uz_cyrl" | "aziza_en"
    language: str             # "ru" | "uz-latn" | "uz-cyrl" | "en"
    emotion_state: str        # "neutral" | "warm" | "curious" | "empathetic"
    conversation_summary: str
    active_context_window: list[dict]
    memory_refs: list[str]    # MongoDB ObjectIds
