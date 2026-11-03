"""Function declarations shown to the LLM, and the code that executes each call.

Every call goes through app.contracts.tools (stub/real switch). The executor,
not the LLM, decides which lead a call acts on: lead_id is always the current
chat's lead, so the model cannot read or change another student's record.
"""
from __future__ import annotations

from typing import Any, Callable

from app.contracts import tools
from app.contracts.models import LeadProfile

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
    _fn("score_lead", "Score the current student as a lead (hot/warm/cold) with reasons.",
        {"profile": _PROFILE}, ["profile"]),
    _fn("upsert_lead", "Save new facts about the current student to the CRM.",
        {"profile": _PROFILE}, ["profile"]),
    _fn("get_lead", "Read the current student's CRM record.", {}, []),
    _fn("get_slots", "List free counsellor slots between two ISO dates.",
        {"date_from": {"type": "string"}, "date_to": {"type": "string"}}, ["date_from", "date_to"]),
    _fn("book_slot", "Book a counsellor slot for the current student. Check `ok` in the result.",
        {"slot_id": {"type": "string"}}, ["slot_id"]),
    _fn("send_message", "Send a message to the current student on a channel (mock).",
        {"channel": {"type": "string", "enum": ["web", "whatsapp", "email"]}, "text": {"type": "string"}},
        ["channel", "text"]),
    _fn("schedule_followup", "Schedule a follow-up for the current student.",
        {"when": {"type": "string", "description": "ISO datetime"}, "template": {"type": "string"}},
        ["when", "template"]),
]

TOOL_NAMES = [d["name"] for d in DECLARATIONS]


def _profile(args: dict) -> LeadProfile:
    data = {k: v for k, v in (args.get("profile") or {}).items() if k in LeadProfile.model_fields}
    return LeadProfile(**data)


_EXECUTORS: dict[str, Callable[[dict, int], Any]] = {
    "search_knowledge": lambda a, lead: tools.search_knowledge(str(a["query"])),
    "score_lead": lambda a, lead: tools.score_lead(_profile(a)),
    "upsert_lead": lambda a, lead: tools.upsert_lead(_profile(a), lead_id=lead),
    "get_lead": lambda a, lead: tools.get_lead(lead),
    "get_slots": lambda a, lead: tools.get_slots(str(a["date_from"]), str(a["date_to"])),
    "book_slot": lambda a, lead: tools.book_slot(lead, str(a["slot_id"])),
    "send_message": lambda a, lead: tools.send_message(str(a["channel"]), lead, str(a["text"])),
    "schedule_followup": lambda a, lead: tools.schedule_followup(lead, str(a["when"]), str(a["template"])),
}


def execute(name: str, args: dict, lead_id: int) -> Any:
    """Run one tool call for the current lead. Raises KeyError for unknown tools."""
    return _EXECUTORS[name](args, lead_id)


def to_jsonable(result: Any) -> Any:
    """Pydantic results (or lists of them) -> plain JSON-able data."""
    if isinstance(result, list):
        return [to_jsonable(r) for r in result]
    return result.model_dump() if hasattr(result, "model_dump") else result
