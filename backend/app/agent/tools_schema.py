"""Function declarations shown to the LLM, and the code that executes each call.

Every call goes through app.contracts.tools (stub/real switch). The executor,
not the LLM, decides which lead a call acts on: lead_id is always the current
chat's lead, so the model cannot read or change another student's record.
Refusals are returned as {"ok": False, "error": ...} so the model can recover;
exceptions mean the tool itself failed and are retried by the loop.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from app.agent.verify import TurnEvidence, check_outbound
from app.contracts import tools
from app.contracts.models import LeadProfile

REQUIRED_FIELDS = ["program_interest", "twelfth_percent", "entrance_exam", "city", "budget_lakh", "name"]
FOLLOWUP_TEMPLATES = ["hot_reminder", "warm_nudge", "cold_nurture", "scholarship", "objection"]
STAFF_ROLES = {"counsellor", "admin"}

_PROFILE = {
    "type": "object",
    "description": "Prospective student's details. Include only fields the student actually gave.",
    "properties": {
        "name": {"type": "string"},
        "phone": {"type": "string"},
        "email": {"type": "string"},
        "city": {"type": "string"},
        "program_interest": {"type": "string", "description": "e.g. B.Tech CSE, MBA, B.Des"},
        "twelfth_percent": {"type": "number", "description": "Class 12 percentage, 0-100"},
        "entrance_exam": {"type": "string", "description": "Exam and score, e.g. JEE Main 92 percentile"},
        "budget_lakh": {"type": "number", "description": "Yearly budget in lakh INR"},
        "asked_scholarship": {"type": "boolean"},
    },
}


def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required}}


DECLARATIONS: list[dict] = [
    _fn("search_knowledge", "Search JKLU's verified knowledge base (fees, eligibility, scholarships, "
        "programs, campus, policies). Returns chunks with a `source` to cite.",
        {"query": {"type": "string"}}, ["query"]),
    _fn("score_lead", "Score the current student as a lead (hot/warm/cold) from their saved profile, plus any "
        "new details given here. The score and reasons are saved.", {"profile": _PROFILE}, []),
    _fn("upsert_lead", "Save new facts about the current student to the CRM. Call after each new fact.",
        {"profile": _PROFILE}, ["profile"]),
    _fn("get_lead", "Read the current student's CRM record.", {}, []),
    _fn("get_slots", "List free counsellor slots between two ISO dates.",
        {"date_from": {"type": "string"}, "date_to": {"type": "string"}}, ["date_from", "date_to"]),
    _fn("book_slot", "Book a counsellor slot for the current student. Check `ok` in the result; if false, "
        "offer the `alternatives`.", {"slot_id": {"type": "string", "description": "The slot_id value, digits only"}},
        ["slot_id"]),
    _fn("send_message", "Send a message to the current student on a channel (mock). Facts must come from this "
        "turn's search_knowledge results, or it is refused.",
        {"channel": {"type": "string", "enum": ["web", "whatsapp", "email"]}, "text": {"type": "string"}},
        ["channel", "text"]),
    _fn("schedule_followup", "Schedule a named follow-up for the current student.",
        {"when": {"type": "string", "description": "ISO datetime"},
         "template": {"type": "string", "enum": FOLLOWUP_TEMPLATES}}, ["when", "template"]),
    _fn("opt_out", "Stop all follow-up messages to the current student, at their request.", {}, []),
    _fn("request_fee_waiver", "Ask a counsellor to consider a fee waiver or discount for the current student. "
        "Nothing is granted: it stays pending until a counsellor decides.",
        {"reason": {"type": "string", "description": "The student's reason, in their words"}}, ["reason"]),
    _fn("request_booking_override", "Ask a counsellor to force-book a slot that is taken. Nothing moves until "
        "a counsellor approves.", {"slot_id": {"type": "string"}, "reason": {"type": "string"}},
        ["slot_id", "reason"]),
    _fn("request_bulk_message", "Staff only: ask for approval to send one message to several leads.",
        {"lead_ids": {"type": "array", "items": {"type": "integer"}},
         "channel": {"type": "string", "enum": ["whatsapp", "email"]}, "text": {"type": "string"}},
        ["lead_ids", "channel", "text"]),
]

TOOL_NAMES = [d["name"] for d in DECLARATIONS]


@dataclass
class ToolEnv:
    """What the code, not the model, decides about a tool call."""

    lead_id: int
    role: str = "anonymous"
    session_id: str = ""
    evidence: TurnEvidence = field(default_factory=TurnEvidence)


def _refuse(error: str, **extra) -> dict:
    return {"ok": False, "error": error, **extra}


def _profile_error(data: dict) -> str | None:
    pct, budget = data.get("twelfth_percent"), data.get("budget_lakh")
    if pct is not None and not (isinstance(pct, (int, float)) and 0 <= pct <= 100):
        return "twelfth_percent must be between 0 and 100"
    if budget is not None and not (isinstance(budget, (int, float)) and 0 <= budget <= 1000):
        return "budget_lakh must be a number of lakh between 0 and 1000"
    return None


def _given(args: dict) -> dict:
    return {k: v for k, v in (args.get("profile") or {}).items() if k in LeadProfile.model_fields and k != "channel"}


def _upsert(args: dict, env: ToolEnv) -> Any:
    data = _given(args)
    error = _profile_error(data)
    return _refuse(error) if error else tools.upsert_lead(LeadProfile(**data), lead_id=env.lead_id)


def score_and_save(lead_id: int, given: dict | None = None) -> Any:
    """Score the lead's saved profile plus any new details, and store the result with its reasons."""
    profile = tools.get_lead(lead_id).profile.model_copy(update=given or {})
    score = tools.score_lead(profile)
    tools.update_lead_score(lead_id, score.score, score.tier, score.reasons)
    return score


def _score(args: dict, env: ToolEnv) -> Any:
    data = _given(args)
    error = _profile_error(data)
    return _refuse(error) if error else score_and_save(env.lead_id, data)


def _send(args: dict, env: ToolEnv) -> Any:
    text = str(args["text"])
    verdict = check_outbound(text, env.evidence)
    if not verdict.ok:
        return _refuse(verdict.reason, **verdict.details)
    return tools.send_message(str(args["channel"]), env.lead_id, text)


def _schedule(args: dict, env: ToolEnv) -> Any:
    template = str(args["template"])
    if template not in FOLLOWUP_TEMPLATES:      # free text here would reach the student unverified
        return _refuse("template must be one of the named templates", templates=FOLLOWUP_TEMPLATES)
    return tools.schedule_followup(env.lead_id, str(args["when"]), template)


def _bulk(args: dict, env: ToolEnv) -> Any:
    if env.role not in STAFF_ROLES:
        return _refuse("bulk messages can only be requested by staff")
    return tools.request_bulk_message([int(i) for i in args["lead_ids"]], str(args["channel"]), str(args["text"]),
                                      session_id=env.session_id)


def _slot_id(args: dict) -> str:
    """Models sometimes echo "slot 40" or "slot_40" from the conversation; the id is the number."""
    raw = str(args["slot_id"]).strip()
    match = re.search(r"\d+$", raw)
    return match.group() if match else raw


_EXECUTORS: dict[str, Callable[[dict, ToolEnv], Any]] = {
    "search_knowledge": lambda a, e: tools.search_knowledge(str(a["query"])),
    "score_lead": _score,
    "upsert_lead": _upsert,
    "get_lead": lambda a, e: tools.get_lead(e.lead_id),
    "get_slots": lambda a, e: tools.get_slots(str(a["date_from"]), str(a["date_to"])),
    "book_slot": lambda a, e: tools.book_slot(e.lead_id, _slot_id(a)),
    "send_message": _send,
    "schedule_followup": _schedule,
    "opt_out": lambda a, e: tools.opt_out_lead(e.lead_id),
    "request_fee_waiver": lambda a, e: tools.request_fee_waiver(e.lead_id, str(a["reason"]), session_id=e.session_id),
    "request_booking_override": lambda a, e: tools.request_booking_override(
        e.lead_id, _slot_id(a), str(a["reason"]), session_id=e.session_id),
    "request_bulk_message": _bulk,
}


def execute(name: str, args: dict, env: ToolEnv) -> Any:
    """Run one tool call for the current lead. Raises KeyError for unknown tools."""
    return _EXECUTORS[name](args, env)


def to_jsonable(result: Any) -> Any:
    """Pydantic results (or lists of them) -> plain JSON-able data."""
    if isinstance(result, list):
        return [to_jsonable(r) for r in result]
    return result.model_dump() if hasattr(result, "model_dump") else result


def missing_fields(profile: dict) -> list[str]:
    """Required qualification fields still unknown (SPEC 2.4), including a way to contact the student."""
    missing = [f for f in REQUIRED_FIELDS if profile.get(f) in (None, "")]
    if not profile.get("phone") and not profile.get("email"):
        missing.append("phone or email")
    return missing
