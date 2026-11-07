"""Writes KB-grounded follow-up wording with the LLM, for followups.dispatch_due.

Returns None on any doubt (no KB answer, model error, failed check), and the
dispatcher then sends the fact-free template, so no unverified fact can go out.
"""
from __future__ import annotations

import concurrent.futures
import logging
from typing import Optional

from app.agent import router as agent_router
from app.agent.prompts import WRITER_SYSTEM
from app.agent.verify import TurnEvidence, check_grounding, check_no_false_grant, citations
from app.contracts import tools

log = logging.getLogger(__name__)
WRITER_TIMEOUT_SECONDS = 20
MAX_LENGTH = 800

_PURPOSE = {
    "warm_nudge": ("share one useful fact and invite questions", "{program} placements and highlights"),
    "scholarship": ("explain scholarship eligibility and suggest a counsellor call", "{program} merit scholarship percentage percentile Class 12"),
}
_OBJECTION = {
    "fees": ("address their worry about fees and suggest a counsellor call", "{program} fee structure scholarship"),
    "distance": ("address their worry about distance and suggest a counsellor call", "hostel and transport facilities"),
}


def _write(prompt: str) -> str:
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(agent_router.get_llm().write, WRITER_SYSTEM, prompt).result(timeout=WRITER_TIMEOUT_SECONDS)
    finally:
        pool.shutdown(wait=False)


def compose(template: str, name: Optional[str], program: Optional[str], payload: Optional[dict]) -> Optional[dict]:
    """Return {"text", "citations"} for this follow-up, or None to fall back to the template."""
    objection = (payload or {}).get("objection")
    purpose = _OBJECTION.get(objection) if template == "objection" else _PURPOSE.get(template)
    if purpose is None:
        return None
    goal, query = purpose
    program = program or "undergraduate programs"
    try:
        kb = tools.search_knowledge(query.format(program=program))
        if not kb.answer_found:
            return None
        sources = "\n\n".join(f"[{c.source}]\n{c.text}" for c in kb.chunks)
        text = _write(f"Student: {name or 'there'}. Interested in: {program}. Purpose: {goal}.\n\nSources:\n{sources}").strip()
    except Exception:
        log.warning("follow-up wording failed; using the template", exc_info=True)
        return None
    evidence = TurnEvidence(knowledge=[kb])
    ok = (0 < len(text) <= MAX_LENGTH and check_grounding(text, evidence, "institutional_question").ok
          and check_no_false_grant(text).ok)
    return {"text": text, "citations": citations(text)} if ok else None
