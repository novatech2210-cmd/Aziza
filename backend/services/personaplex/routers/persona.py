from fastapi import APIRouter, HTTPException
from ..models.schema import Persona, PromptBuildRequest, SessionContext, EmotionalState
from ..services.personaplex_core import PersonaPlexService

router = APIRouter(prefix="/persona", tags=["personaplex"])
service = PersonaPlexService()

@router.post("/build-prompt")
async def build_prompt(request: PromptBuildRequest):
    try:
        # Ensure service is connected (fast check)
        if not service.redis.redis:
            await service.startup()
        prompt = await service.build_prompt(request.session_id, request.user_message)
        return {"prompt": prompt, "session_id": request.session_id}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/update-context")
async def update_context(session: SessionContext):
    await service.redis.update_session_context(session.session_id, session.model_dump())
    return {"status": "ok"}

@router.get("/state/{session_id}")
async def get_state(session_id: str):
    context = await service.redis.get_session_context(session_id)
    return context or {"status": "not_found"}

@router.post("/semantic-recall")
async def semantic_recall(session_id: str, query: str):
    memories = await service.get_relevant_memories(query, session_id)
    return {"memories": memories}

@router.post("/emotion-update")
async def update_emotion(session_id: str, emotion: EmotionalState):
    await service.update_emotional_state(session_id, emotion)
    return {"status": "ok"}
