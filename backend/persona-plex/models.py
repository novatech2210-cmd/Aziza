from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class Persona(BaseModel):
    id: str = Field(..., alias="_id")
    name: str
    description: str
    system_prompt: str
    voice_preset: Optional[str] = "default"
    metadata: Dict[str, Any] = {}

class MemoryEntry(BaseModel):
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    content: str
    sender: str # "user" or "ai"
    metadata: Dict[str, Any] = {}

class SessionContext(BaseModel):
    session_id: str
    persona_id: str
    history: List[MemoryEntry] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class LoadPersonaRequest(BaseModel):
    session_id: str
    user_id: str
    persona_id: str
    language: str
    emotion_state: str = "neutral"

class SwitchPersonaRequest(BaseModel):
    session_id: str
    persona_id: Optional[str] = None
    language: Optional[str] = None
    emotion_state: Optional[str] = None

class MemoryStoreRequest(BaseModel):
    session_id: str
    content: str
    sender: str

class PromptBuildRequest(BaseModel):
    session_id: str
    user_message: str = ""
