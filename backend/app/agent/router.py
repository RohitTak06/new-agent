# Owner: Rohit. Agent loop, planner, retries, reasoning trace, streaming chat.
from fastapi import APIRouter

from app.contracts import tools

router = APIRouter()


@router.get("/health")
def health():
    return {"module": "agent", "ok": True}


@router.post("/chat")
def chat(message: str):
    # Placeholder: replace with the real plan -> act -> verify loop.
    result = tools.search_knowledge(message)
    return {"answer_found": result.answer_found, "sources": [c.source for c in result.chunks]}
