"""Agent HTTP API: POST /agent/chat streams the agent loop as Server-Sent Events."""
from __future__ import annotations

import json
import uuid
from functools import lru_cache
from typing import Iterator, Literal, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.llm import LLM, GeminiLLM
from app.agent.loop import AgentLoop, TurnContext
from app.contracts import tools
from app.contracts.models import Lead, LeadProfile
from app.crm import service as crm

router = APIRouter()

HISTORY_TURNS = 10


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: Optional[str] = Field(default=None, max_length=64)
    lead_id: Optional[int] = None
    channel: Literal["web", "whatsapp", "email"] = "web"


@lru_cache(maxsize=1)
def get_llm() -> LLM:
    """The production LLM; tests override this dependency-style via `router.get_llm`."""
    return GeminiLLM()


@router.get("/health")
def health():
    return {"module": "agent", "ok": True}


@router.post("/chat")
def chat(req: ChatRequest):
    """Run one agent turn and stream its events (`text/event-stream`, SPEC 2.2)."""
    lead = _resolve_lead(req)
    session_id = req.session_id or uuid.uuid4().hex
    history = _history(lead.id)
    crm.add_interaction(lead.id, actor="student", channel=req.channel, direction="inbound",
                        message=req.message, meta={"session_id": session_id})
    ctx = TurnContext(message=req.message, lead_id=lead.id, session_id=session_id,
                      channel=req.channel, history=history,
                      lead_profile=lead.profile.model_dump(exclude={"channel"}))
    return StreamingResponse(
        _stream(ctx), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _resolve_lead(req: ChatRequest) -> Lead:
    if req.lead_id is None:
        return tools.upsert_lead(LeadProfile(channel=req.channel))   # anonymous lead for a new chat
    try:
        return tools.get_lead(req.lead_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Lead {req.lead_id} not found")


def _history(lead_id: int) -> list[dict]:
    rows = crm.list_interactions(lead_id)[-HISTORY_TURNS:]
    return [{"role": "student" if r["direction"] == "inbound" else "agent", "text": r["message"]}
            for r in rows]


def _stream(ctx: TurnContext) -> Iterator[str]:
    """Run the loop, audit-log each event, store the reply, and format SSE frames."""
    try:
        loop = AgentLoop(get_llm())
        events = loop.run(ctx)
    except Exception as exc:  # e.g. missing LLM config: report it as a stream, never a 500
        events = iter([
            {"type": "error", "step": 0, "ts": "", "data": {"error": type(exc).__name__, "detail": str(exc)}},
            {"type": "final", "step": 0, "ts": "", "data": {
                "text": "The assistant is not available right now. Please try again later.",
                "intent": "unknown", "citations": [], "escalated": False, "approval_id": None}},
        ])
    for event in events:
        try:
            _audit(event, ctx)
            if event["type"] == "final":
                crm.add_interaction(ctx.lead_id, actor="agent", channel=ctx.channel, direction="outbound",
                                    message=event["data"]["text"],
                                    meta={"session_id": ctx.session_id,
                                          **{k: v for k, v in event["data"].items() if k != "text"}})
        except Exception as exc:  # persistence must not cut the student's stream
            yield _frame({"type": "error", "step": event["step"], "ts": event["ts"],
                          "data": {"error": "persistence_failed", "detail": f"{type(exc).__name__}: {exc}"[:300]}})
        if event["type"] == "final":
            event["data"].update(session_id=ctx.session_id, lead_id=ctx.lead_id)
        yield _frame(event)


def _frame(event: dict) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n"


def _audit(event: dict, ctx: TurnContext) -> None:
    """Write every event to audit_log. Message deltas are skipped: `final` holds the full text."""
    if event["type"] == "message":
        return
    data = event["data"]
    crm.log_event(
        actor="agent",
        event_type=event["type"],
        tool_name=data.get("name") or data.get("target"),
        input=data.get("args") if event["type"] == "tool_call" else None,
        output=data,
        reasoning_step=data.get("reason") or data.get("intent"),
        request_id=f"{ctx.session_id}:{event['step']}",
        lead_id=ctx.lead_id,
        session_id=ctx.session_id,
    )
