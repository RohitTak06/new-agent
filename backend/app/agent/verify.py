"""Deterministic verifiers run on every drafted answer before the user sees it.

These are plain code checks, not prompting: an answer that fails them is either
sent back to the LLM once with the reason (replan) or replaced by an escalation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from app.contracts.models import ApprovalRequest, BookingResult, KnowledgeResult, LeadScore

NOT_IN_KB = "[NOT_IN_KB]"

# Intents whose answers state institutional facts and therefore need KB grounding.
GROUNDED_INTENTS = {"institutional_question", "sensitive_request"}

# One source in brackets, or several separated by commas or semicolons: [a.md#x, b.md#y].
_SOURCE = r"[^\[\]\s,;]+\.md(?:#[^\[\]\s,;]*)?"
_CITATION = re.compile(rf"\[\s*({_SOURCE}(?:\s*[,;]\s*{_SOURCE})*)\s*\]")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_FEE_GRANT = re.compile(r"\b(?:waiver|discount|concession)\b", re.IGNORECASE)
GRANTING_ACTIONS = {"fee_waiver", "booking_override"}
_BOOKING_CLAIM = re.compile(r"\b(booked|confirmed|reserved|scheduled)\b", re.IGNORECASE)
_NEGATION = re.compile(r"\b(not|n't|unable|couldn't|could not|cannot|can't|no longer)\b", re.IGNORECASE)
_GRANT = re.compile(
    r"\byour\s+(?:\w+\s+){0,3}(?:waiver|discount|scholarship|exception|seat|admission|request|concession)\s+"
    r"(?:\w+\s+){0,2}(?:approved|granted|confirmed|waived|accepted)\b"
    r"|\bi\s+(?:have\s+|'ve\s+|can\s+|will\s+|am\s+going\s+to\s+)(?:\w+\s+)?(?:approved?|grant(?:ed)?|waived?|guarantee[ds]?)\b"
    r"|\byou\s+(?:have\s+been|'ve\s+been|are|will\s+be)\s+(?:\w+\s+)?(?:approved|granted|awarded|guaranteed|admitted)\b"
    r"|\byou(?:\s+will|\s+also)?\s+qualify\s+for\s+(?:an?\s+|the\s+)?(?:\S+\s+)?(?:\w+\s+)?scholarship\b"
    r"|\byou(?:'re|\s+are)\s+eligible\s+for\s+(?:an?\s+|the\s+)?(?:\S+\s+)?(?:\w+\s+)?scholarship\b"
    r"|\bfree\s+seat\b|\bguaranteed\s+(?:an?\s+)?(?:seat|admission|scholarship)\b",
    re.IGNORECASE,
)
_GRANT_NEGATION = re.compile(r"\b(not|no|never|unable|cannot|can't|won't|doesn't|don't|if|whether)\b", re.IGNORECASE)
# Money and percentages: the figures a model most easily invents outside an institutional answer.
_FIGURE = re.compile(r"(?:INR|Rs\.?|₹)\s*\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s*(?:%|(?:lakhs?|lacs?|percent)\b)",
                     re.IGNORECASE)


@dataclass
class TurnEvidence:
    """Tool results gathered during one agent turn."""

    knowledge: list[KnowledgeResult] = field(default_factory=list)
    bookings: list[BookingResult] = field(default_factory=list)
    approvals: list[ApprovalRequest] = field(default_factory=list)
    tool_text: list[str] = field(default_factory=list)    # slot/booking results, for outbound message checks
    profile: Optional[dict] = None                        # lead profile after this turn's upsert_lead
    score: Optional[LeadScore] = None
    escalation: Optional[Any] = None                      # approval created by a fallback path
    request_ids: set[int] = field(default_factory=set)    # this lead's requests from before this turn

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
    sources = (s.strip() for group in _CITATION.findall(text) for s in re.split(r"[,;]", group))
    return list(dict.fromkeys(sources))


def _numbers(text: str) -> set[str]:
    out = set()
    for raw in _NUMBER.findall(text):
        n = raw.replace(",", "").rstrip(".")
        if "." in n:
            n = n.rstrip("0").rstrip(".")
        out.add(n)
    return out


def _about_a_request(evidence: TurnEvidence, intent: str) -> bool:
    return bool(evidence.approvals or (intent == "sensitive_request" and evidence.request_ids))


def _only_reports_a_request(answer: str, cited: list[str], evidence: TurnEvidence, intent: str) -> bool:
    """Saying a request was filed, or where it stands, needs no source as long as it states no fact or figure."""
    if cited or not _about_a_request(evidence, intent):
        return False
    ids = {str(a.approval_id) for a in evidence.approvals} | {str(i) for i in evidence.request_ids}
    return not (_numbers(answer) - ids)


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

    if _only_reports_a_request(answer, cited, evidence, intent):
        return Verdict("grounding", True, "reports the student's request; no institutional claims made")
    if _about_a_request(evidence, intent) and not evidence.found_chunks:     # it's on file, so only the wording needs fixing
        return Verdict("grounding", False, "answer states a fact or figure with no knowledge-base source", "replan")
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


def _approved_by_counsellor(claim: str, approved_actions: set[str]) -> bool:
    """Is this claim backed by an approval of that kind? Answering a question grants nothing, and seats never come from here."""
    if _FEE_GRANT.search(claim):
        return "fee_waiver" in approved_actions
    if re.search(r"\brequest\b", claim, re.IGNORECASE):
        return bool(approved_actions & GRANTING_ACTIONS)
    return False


def check_no_false_grant(answer: str, approved_actions: Optional[set[str]] = None) -> Verdict:
    """Only counsellors grant things. Reject a draft that promises something no counsellor approved for this lead."""
    claims = []
    for m in _GRANT.finditer(answer):
        if not _GRANT_NEGATION.search(answer[max(0, m.start() - 25):m.start()])                 and not _approved_by_counsellor(m.group(0), approved_actions or set()):
            claims.append(m.group(0))
    if claims:
        return Verdict("no_false_grant", False, "answer promises something only a counsellor can grant", "replan",
                       {"claims": claims})
    return Verdict("no_false_grant", True, "no grant promised")


def check_figures(answer: str, evidence: TurnEvidence, known_text: str = "") -> Verdict:
    """Any intent: money and percentages must come from the KB, this conversation or tool results."""
    known = _numbers(" ".join(c.text for c in evidence.found_chunks)) | _numbers(known_text)
    unknown = sorted(n for raw in _FIGURE.findall(answer) for n in _numbers(raw) if n not in known)
    if unknown:
        return Verdict("figures", False, "answer contains money or percentage figures with no source", "replan",
                       {"ungrounded_numbers": unknown})
    return Verdict("figures", True, "all figures have a source")


def check_outbound(text: str, evidence: TurnEvidence) -> Verdict:
    """Text the model wants to send on a channel: citations and numbers must trace to this turn's tool results."""
    grant = check_no_false_grant(text)
    if not grant.ok:
        return grant
    unknown_sources = [s for s in citations(text) if s not in evidence.sources]
    if unknown_sources:
        return Verdict("outbound", False, "message cites sources that were not retrieved", "replan",
                       {"unknown_sources": unknown_sources})
    known = _numbers(" ".join(c.text for c in evidence.found_chunks)) | _numbers(" ".join(evidence.tool_text))
    unknown = sorted(_numbers(_CITATION.sub("", text)) - known)
    if unknown:
        return Verdict("outbound", False, "message contains numbers with no source", "replan",
                       {"ungrounded_numbers": unknown})
    return Verdict("outbound", True, "message passes checks")


def verify_answer(answer: str, evidence: TurnEvidence, intent: str, question: str = "",
                  known_text: str = "", approved_actions: Optional[set[str]] = None) -> list[Verdict]:
    """Run every verifier; the loop acts on the first failure."""
    return [check_grounding(answer, evidence, intent, question), check_booking(answer, evidence),
            check_no_false_grant(answer, approved_actions), check_figures(answer, evidence, known_text or question)]
