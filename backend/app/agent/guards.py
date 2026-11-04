"""Checks on the student's message that run before any model call.

Opt-out is a compliance action, so it must not depend on the model understanding
it. Injection attempts get a fixed refusal, so there is nothing to talk the model
into. Attacks these patterns miss are still contained: the model has no tool that
grants anything, the lead is set by code, and every answer goes through verify.py.
"""
from __future__ import annotations

import re
from typing import Literal, Optional

OPT_OUT_MSG = ("Done: you've been opted out and we won't send you any more follow-up messages. "
               "You can still chat here any time if you have questions.")
INJECTION_MSG = ("I can't change or bypass the admissions rules, and I can't grant seats, waivers or exceptions: "
                 "counsellors decide those. I'm happy to answer questions about programs, fees, eligibility or "
                 "scholarships, or to book a counsellor session.")

_CONTACT_VERBS = r"(?:messag\w*|contact\w*|email\w*|e-mail\w*|text\w*|whatsapp\w*|call\w*|send\w*|spam\w*)"
_OPT_OUT = re.compile(
    rf"\b(?:unsubscribe|stop\s+{_CONTACT_VERBS}|(?:don'?t|do\s+not|never)\s+{_CONTACT_VERBS}(?:\s+\w+)?\s+me"
    rf"|remove\s+me\s+from|opt[\s-]?(?:me\s+)?out(?!\s+of\s+(?:the\s+)?(?:hostel|mess|transport|course|program)))\b",
    re.IGNORECASE,
)
_QUESTION = re.compile(r"^\s*(?:how|what|why|when|where|does|do|is|will|can|could|if)\b.*\?\s*$", re.IGNORECASE | re.S)

_FILLER = r"(?:(?:all|any|the|your|my|previous|prior|above|earlier|these|those|of|every)\s+)*"
_INJECTION = re.compile(
    rf"\b(?:ignore|disregard|forget|override|bypass)\s+{_FILLER}(?:rules?|instructions?|prompts?|guidelines?|polic(?:y|ies)|restrictions?)\b"
    r"|\b(?:reveal|show|print|repeat|tell\s+me|what\s+(?:is|are))\s+(?:me\s+)?(?:your\s+|the\s+)*(?:system\s+prompt|(?:hidden\s+|secret\s+)?instructions|prompt)\b"
    r"|\bsystem\s+prompt\b|\bdeveloper\s+mode\b|\bjailbreak\b"
    r"|\byou\s+are\s+now\s+(?:an?\s+|in\s+)"
    r"|\bpretend\s+(?:you\s+are|you'?re|to\s+be)\b"
    r"|\bact\s+as\s+(?:an?\s+|the\s+)?(?:admin\w*|counsell?or|dean|director|developer)\b"
    r"|\bas\s+(?:an?\s+|the\s+)?(?:admin\w*|dean|director|counsell?or)\b.{0,60}\b(?:approve|grant|waive)\b",
    re.IGNORECASE | re.S,
)


def check_message(message: str) -> Optional[Literal["opt_out", "injection"]]:
    """Classify a message that must not reach the model. Injection wins: it may hide a fake opt-out."""
    if _INJECTION.search(message):
        return "injection"
    if _OPT_OUT.search(message) and not _QUESTION.match(message):
        return "opt_out"
    return None
