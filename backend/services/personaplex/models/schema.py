from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

class Persona(BaseModel):
    persona_id: str
    name: str
    system_prompt: str
    voice_prompt: Optional[str] = None
    language: str = "en"
    traits: Dict[str, str] = Field(default_factory=dict)

class EmotionalState(BaseModel):
    primary: str = "neutral"
    intensity: float = 0.5
    valence: float = 0.0  # -1.0 (negative) to +1.0 (positive)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

class VectorMemory(BaseModel):
    memory_id: str
    session_id: str
    user_id: str
    content: str
    embedding: List[float]
    metadata: Dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class PersonaEvolution(BaseModel):
    persona_id: str
    traits: Dict[str, float]  # trait -> strength
    adaptation_history: List[Dict] = Field(default_factory=list)

class SessionContext(BaseModel):
    session_id: str
    user_id: str
    persona_id: str
    language: str
    emotion_state: str = "neutral"
    conversation_summary: str = ""
    active_context_window: List[Dict] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    memory_refs: List[str] = Field(default_factory=list)

class PromptBuildRequest(BaseModel):
    session_id: str
    user_message: str
    temperature: float = 0.7
    max_tokens: int = 1024
