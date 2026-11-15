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

_CONTACT_VERBS = r"(?:messag\w*|contact\w*|email\w*|e-mail\w*|text\w*|whatsapp\w*|call\w*|send\w*|spam\w*|ping\w*)"
_LIST_WORDS = r"(?:messages?|emails?|texts?|spam|updates?|follow[\s-]?ups?|reminders?|communications?|marketing|mailing\s+list|list|notifications?)"

# Opt-out is a hard stop that only a counsellor can undo, so a "don't ... me" sentence counts only when nothing
# narrows it: "don't email me the brochure, WhatsApp is better" and "stop texting me at night" are preferences, not opt-outs.
_TAIL_WORDS = rf"(?:again|anymore|any\s+more|ever|at\s+all|please|pls|now|thanks|thank\s+you|thx|from\s+now\s+on|{_LIST_WORDS}|about\s+(?:admissions|this|jklu))"
_STOP_SENTENCE = re.compile(
    rf"^(?P<lead>.*?)\b(?:stop|(?:don'?t|do\s+not|never)(?:\s+(?:ever|again))?)\s+{_CONTACT_VERBS}(?:\s+(?:to|with))?\s+(?:me|us)"
    rf"(?:[\s,]+{_TAIL_WORDS})*[\s,]*$",
    re.IGNORECASE,
)
_CONDITIONAL_LEAD = re.compile(r"\b(?:if|when|unless|until|why|want\s+you\s+to\s+keep|don'?t\s+want|do\s+not\s+want)\b", re.IGNORECASE)
_STRONG_OPT_OUT = re.compile(
    rf"\bunsubscribe\b"
    rf"|\bremove\s+me\s+from\b"
    rf"|\bopt[\s-]?(?:me\s+)?out\b(?!\s+of\b)"
    rf"|\bopt[\s-]?(?:me\s+)?out\s+of\s+(?:your\s+|these\s+|all\s+|the\s+|jklu'?s?\s+)*{_LIST_WORDS}\b",
    re.IGNORECASE,
)
_SENTENCES = re.compile(r"[.!;\n]+")
_QUESTION = re.compile(r"^\s*(?:how|what|why|when|where|does|do|is|will|can|could|if)\b.*\?\s*$", re.IGNORECASE | re.S)

_FILLER = r"(?:(?:all|any|the|your|my|previous|prior|above|earlier|these|those|of|every)\s+)*"
_INJECTION = re.compile(
    rf"\b(?:ignore|disregard|forget|override|bypass)\s+{_FILLER}(?:rules?|instructions?|prompts?|guidelines?|polic(?:y|ies)|restrictions?)\b"
    # Only the assistant's own instructions: "what are the instructions for the application form?" is a real question.
    r"|\b(?:reveal|show|print|repeat|tell\s+me|give\s+me|what\s+(?:is|are|were))\s+(?:me\s+)?(?:all\s+)?"
    r"(?:(?:your|the\s+assistant'?s|its)\s+(?:\w+\s+)?(?:instructions|prompt|rules)\b"
    r"|(?:the\s+|your\s+)?(?:hidden|secret|original|initial|internal)\s+(?:instructions|prompt|rules)\b)"
    r"|\bsystem\s+prompt\b|\bdeveloper\s+mode\b|\bjailbreak\b"
    r"|\byou\s+are\s+now\s+(?:an?\s+|in\s+)"
    r"|\bpretend\s+(?:you\s+are|you'?re|to\s+be)\b"
    r"|\bact\s+as\s+(?:an?\s+|the\s+)?(?:admin\w*|counsell?or|dean|director|developer)\b"
    r"|\bas\s+(?:an?\s+|the\s+)?(?:admin\w*|dean|director|counsell?or)\b.{0,60}\b(?:approve|grant|waive)\b"
    # Personas and "modes" that claim to drop the rules (DAN and its cousins).
    r"|\bdo\s+anything\s+now\b|\b(?:with|has|have|without)\s+(?:no|any)\s+(?:rules|restrictions|limits|filters|guidelines)\b"
    r"|\b(?:let'?s|we'?ll|we\s+will)\s+play\s+a\s+game\b|\brole[\s-]?play\b|\bunfiltered\b|\buncensored\b"
    # Fake turns and tags: the student's words can't close their own tag or speak as the system.
    r"|</?\s*student_message\s*>|^\s*(?:system|assistant|developer)\s*:"
    # Hidden orders: decode-and-obey, and notes addressed to the AI inside a question.
    r"|\bdecode\b.{0,60}\b(?:follow|do|execute|obey|run)\b|\bnote\s+to\s+the\s+(?:ai|assistant|bot|model)\b"
    # "Ignore the instructions" in Hindi.
    r"|(?:निर्देश|नियम)\S*.{0,30}(?:अनदेखा|नज़रअंदाज़|नजरअंदाज|भूल)",
    re.IGNORECASE | re.S | re.M,
)
_DAN = re.compile(r"\bDAN\b")          # the persona's name; case-sensitive so the name "Dan" isn't caught


def _is_opt_out(message: str) -> bool:
    if _QUESTION.match(message):
        return False
    if _STRONG_OPT_OUT.search(message):
        return True
    for sentence in _SENTENCES.split(message):
        m = _STOP_SENTENCE.match(sentence.strip())
        if m and not _CONDITIONAL_LEAD.search(m.group("lead")):
            return True
    return False


def check_message(message: str) -> Optional[Literal["opt_out", "injection"]]:
    """Classify a message that must not reach the model. Injection wins: it may hide a fake opt-out."""
    if _INJECTION.search(message) or _DAN.search(message):
        return "injection"
    if _is_opt_out(message):
        return "opt_out"
    return None
