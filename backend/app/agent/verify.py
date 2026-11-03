"""Deterministic verifiers run on every drafted answer before the user sees it.

These are plain code checks, not prompting: an answer that fails them is either
sent back to the LLM once with the reason (replan) or replaced by an escalation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.contracts.models import BookingResult, KnowledgeResult

NOT_IN_KB = "[NOT_IN_KB]"

# Intents whose answers state institutional facts and therefore need KB grounding.
GROUNDED_INTENTS = {"institutional_question", "sensitive_request"}

_CITATION = re.compile(r"\[([^\[\]\s]+\.md(?:#[^\[\]\s]*)?)\]")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_BOOKING_CLAIM = re.compile(r"\b(booked|confirmed|reserved|scheduled)\b", re.IGNORECASE)
_NEGATION = re.compile(r"\b(not|n't|unable|couldn't|could not|cannot|can't|no longer)\b", re.IGNORECASE)


@dataclass
class TurnEvidence:
    """Tool results gathered during one agent turn."""

    knowledge: list[KnowledgeResult] = field(default_factory=list)
    bookings: list[BookingResult] = field(default_factory=list)

    @property
    def found_chunks(self):
        return [c for k in self.knowledge if k.answer_found for c in k.chunks]

    @property
    def sources(self) -> set[str]:
        return {c.source for c in self.found_chunks}


@dataclass
class Verdict:
    """Result of one verifier. `action` says what the loop should do on failure."""

    check: str
    ok: bool
    reason: str
    action: Literal["none", "replan", "escalate"] = "none"
    details: dict = field(default_factory=dict)

    def as_event(self) -> dict:
        return {"check": self.check, "ok": self.ok, "reason": self.reason,
                "action": self.action, **self.details}


def citations(text: str) -> list[str]:
    """Return the `[file.md#anchor]` sources cited in `text`, in order, unique."""
    return list(dict.fromkeys(_CITATION.findall(text)))


def _numbers(text: str) -> set[str]:
    out = set()
    for raw in _NUMBER.findall(text):
        n = raw.replace(",", "").rstrip(".")
        if "." in n:
            n = n.rstrip("0").rstrip(".")
        out.add(n)
    return out


def check_grounding(answer: str, evidence: TurnEvidence, intent: str, question: str = "") -> Verdict:
    """Institutional answers must be backed by this turn's KB results.

    Fails when the model says the KB has no answer, when no search returned
    `answer_found=True`, when nothing is cited, when a cited source was not
    retrieved, or when a number in the answer is absent from the retrieved text
    (numbers the student typed themselves are allowed).
    """
    if NOT_IN_KB in answer:
        return Verdict("grounding", False, "model reports the KB does not answer this", "escalate")

    cited = citations(answer)
    needs_grounding = intent in GROUNDED_INTENTS or bool(cited)
    if not needs_grounding:
        return Verdict("grounding", True, "no institutional claims for this intent")

    if not evidence.found_chunks:
        return Verdict("grounding", False, "no knowledge-base result supports this answer", "escalate")
    if not cited:
        return Verdict("grounding", False, "answer cites no knowledge-base source", "replan")

    unknown = [s for s in cited if s not in evidence.sources]
    if unknown:
        return Verdict("grounding", False, "answer cites sources that were not retrieved", "replan",
                       {"unknown_sources": unknown})

    body = _CITATION.sub("", answer)
    kb_numbers = _numbers(" ".join(c.text for c in evidence.found_chunks))
    ungrounded = sorted(_numbers(body) - kb_numbers - _numbers(question))
    if ungrounded:
        return Verdict("grounding", False, "answer contains numbers not found in the cited text", "replan",
                       {"ungrounded_numbers": ungrounded})

    return Verdict("grounding", True, "all claims cite retrieved sources", details={"citations": cited})


def check_booking(answer: str, evidence: TurnEvidence) -> Verdict:
    """Never claim a booking unless a `book_slot` call this turn returned ok=True."""
    claims = []
    for m in _BOOKING_CLAIM.finditer(answer):
        window = answer[max(0, m.start() - 30):m.start()]
        if not _NEGATION.search(window):
            claims.append(m.group(0))
    if not claims:
        return Verdict("booking", True, "no booking claimed")
    if any(b.ok for b in evidence.bookings):
        return Verdict("booking", True, "booking claim backed by a successful book_slot")
    return Verdict("booking", False, "answer claims a booking but no book_slot succeeded", "replan",
                   {"claims": claims})


def verify_answer(answer: str, evidence: TurnEvidence, intent: str, question: str = "") -> list[Verdict]:
    """Run every verifier; the loop acts on the first failure."""
    return [check_grounding(answer, evidence, intent, question), check_booking(answer, evidence)]
