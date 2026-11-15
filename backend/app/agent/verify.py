"""Deterministic verifiers run on every drafted answer before the user sees it.

These are plain code checks, not prompting: an answer that fails them is either
sent back to the LLM once with the reason (replan) or replaced by an escalation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from app.contracts.models import ApprovalRequest, BookingResult, CancelResult, CounsellorInfo, KnowledgeResult, LeadScore

NOT_IN_KB = "[NOT_IN_KB]"

# Intents whose answers state institutional facts and therefore need KB grounding.
GROUNDED_INTENTS = {"institutional_question", "sensitive_request"}

# One source in brackets, or several separated by commas or semicolons: [a.md#x, b.md#y].
_SOURCE = r"[^\[\]\s,;]+\.md(?:#[^\[\]\s,;]*)?"
_CITATION = re.compile(rf"\[\s*({_SOURCE}(?:\s*[,;]\s*{_SOURCE})*)\s*\]")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
# "Class 12", "12th marks" and the like name a school year. Only 10 and 12, so a date like "12th March" stays checked.
_SCHOOL_YEAR = re.compile(
    r"\b(?:class|grade|std\.?|standard)\s+(?:10|12)(?:th)?\b"
    r"|\b(?:10|12)th\s+(?=(?:class|grade|standard|board|marks|exams?|results?|subjects?)\b)",
    re.IGNORECASE,
)
_FEE_GRANT = re.compile(r"\b(?:waiver|discount|concession)\b", re.IGNORECASE)
GRANTING_ACTIONS = {"fee_waiver", "booking_override"}
_BOOKING_CLAIM = re.compile(r"\b(booked|confirmed|reserved|scheduled)\b", re.IGNORECASE)
_CANCEL_CLAIM = re.compile(r"\b(cancell?ed|released|removed|deleted|freed(?:\s+up)?)\b", re.IGNORECASE)
# A booking word is a booking claim only in a sentence about a session: "as confirmed on the official page",
# "seats are reserved for..." and "classes are scheduled to begin..." state facts, not bookings.
_BOOKING_CONTEXT = re.compile(
    r"\b(?:sessions?|slots?|appointments?|meetings?|calls?|counsell?(?:or|ing)\w*|bookings?|visits?|consultations?)\b"
    r"|\b(?:you(?:'re|\s+are)|i(?:'ve|\s+have))\s+(?:\w+\s+)?(?:booked|reserved|scheduled|confirmed)\b"
    r"|\b(?:Ms|Mr|Mrs|Dr)\.?\s+[A-Z]"
    r"|\b\d{1,2}[:.]\d{2}\b|\b\d{1,2}\s*(?:am|pm)\b|\btomorrow\b"
    r"|\b(?:mon|tues|wednes|thurs|fri|satur|sun)day\b",
    re.IGNORECASE,
)
# Any video-meeting link. A link in a reply must be one the calendar issued, never one the model wrote.
_MEETING_LINK = re.compile(r"https?://(?:meet\.jklu\.example|meet\.google\.com|meet\.jit\.si|[\w.-]*zoom\.us)/[^\s)\]>,]*",
                           re.IGNORECASE)
_FOLLOWUP_ONLY = re.compile(r"\b(?:follow[\s-]?ups?|reminders?)\b", re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_NEGATION = re.compile(r"\b(not|n't|unable|couldn't|could not|cannot|can't|no longer)\b", re.IGNORECASE)
_GRANT = re.compile(
    r"\byour\s+(?:\w+\s+){0,3}(?:waiver|discount|scholarship|exception|seat|admission|request|concession)\s+"
    r"(?:\w+\s+){0,2}(?:approved|granted|confirmed|waived|accepted)\b"
    r"|\bi\s+(?:have\s+|'ve\s+|can\s+|will\s+|am\s+going\s+to\s+)(?:\w+\s+)?(?:approved?|grant(?:ed)?|waived?|guarantee[ds]?)\b"
    r"|\byou\s+(?:have\s+been|'ve\s+been|are|will\s+be)\s+(?:\w+\s+)?(?:approved|granted|awarded|guaranteed|admitted)\b"
    r"|\byou(?:\s+will|\s+also)?\s+qualify\s+for\s+(?:an?\s+|the\s+)?(?:\S+\s+)?(?:\w+\s+)?scholarship\b"
    r"|\bqualifies\s+you\s+for\s+(?:an?\s+|the\s+)?(?:\S+\s+)?(?:\w+\s+)?scholarship\b"
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
    cancellations: list[CancelResult] = field(default_factory=list)
    counsellors: list[CounsellorInfo] = field(default_factory=list)  # from get_counsellors this turn
    approvals: list[ApprovalRequest] = field(default_factory=list)
    tool_text: list[str] = field(default_factory=list)    # slot/booking results, for outbound message checks
    profile: Optional[dict] = None                        # lead profile after this turn's upsert_lead
    score: Optional[LeadScore] = None
    escalation: Optional[Any] = None                      # approval created by a fallback path
    request_ids: set[int] = field(default_factory=set)    # this lead's requests from before this turn
    meeting_urls: set[str] = field(default_factory=set)   # links of sessions the student already held at the start

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
    action: Literal["none", "replan", "escalate", "refuse"] = "none"
    details: dict = field(default_factory=dict)

    def as_event(self) -> dict:
        return {"check": self.check, "ok": self.ok, "reason": self.reason,
                "action": self.action, **self.details}


def citations(text: str) -> list[str]:
    """Return the `[file.md#anchor]` sources cited in `text`, in order, unique."""
    sources = (s.strip() for group in _CITATION.findall(text) for s in re.split(r"[,;]", group))
    return list(dict.fromkeys(sources))


def _without_school_years(text: str) -> str:
    """Drop school-year names like "Class 12" or "12th marks": they name a year, they don't state a figure."""
    return _SCHOOL_YEAR.sub(" ", text)


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


_TITLE = re.compile(r"^(?:Dr|Mr|Mrs|Ms|Prof)\.?\s+", re.IGNORECASE)


def _answers_from_counsellor_list(answer: str, cited: list[str], evidence: TurnEvidence, question: str) -> bool:
    """'Who is Mr. Sunil Mathur?' is answered by the counsellor list, not the KB: the answer must name a counsellor
    that get_counsellors returned this turn, cite nothing, and use no number the list or the student didn't give."""
    if cited or not evidence.counsellors:
        return False
    text = answer.lower()
    if not any(_TITLE.sub("", c.name).lower() in text for c in evidence.counsellors):
        return False
    known = _numbers(" ".join(evidence.tool_text)) | _numbers(question)
    return not (_numbers(_without_school_years(answer)) - known)


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

    if _answers_from_counsellor_list(answer, cited, evidence, question):
        return Verdict("grounding", True, "answers from the counsellor list; no institutional claims made")
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

    body = _without_school_years(_CITATION.sub("", answer))
    kb_numbers = _numbers(" ".join(c.text for c in evidence.found_chunks))
    ungrounded = sorted(_numbers(body) - kb_numbers - _numbers(question))
    if ungrounded:
        return Verdict("grounding", False, "answer contains numbers not found in the cited text", "replan",
                       {"ungrounded_numbers": ungrounded})

    return Verdict("grounding", True, "all claims cite retrieved sources", details={"citations": cited})


def _booking_claims(answer: str, claim: re.Pattern = _BOOKING_CLAIM) -> list[str]:
    claims = []
    for sentence in _SENTENCE_SPLIT.split(answer):
        about_session = _BOOKING_CONTEXT.search(sentence)
        if not about_session or (_FOLLOWUP_ONLY.search(sentence) and not re.search(r"\bsessions?|slots?|appointments?\b",
                                                                                        sentence, re.IGNORECASE)):
            continue
        for m in claim.finditer(sentence):
            if not _NEGATION.search(sentence[max(0, m.start() - 30):m.start()]):
                claims.append(m.group(0))
    return claims


def check_booking(answer: str, evidence: TurnEvidence) -> Verdict:
    """Never claim a booking unless a `book_slot` call this turn returned ok=True, nor a cancellation
    unless a `cancel_booking` call this turn returned ok=True."""
    issued = evidence.meeting_urls | {b.slot.meeting_url for b in evidence.bookings if b.slot and b.slot.meeting_url}
    links = [m.group(0).rstrip(".") for m in _MEETING_LINK.finditer(answer)]
    unknown = [link for link in links if link not in issued]
    if unknown:
        return Verdict("booking", False, "answer gives a meeting link that no booking issued", "replan",
                       {"links": unknown})
    cancelled = _booking_claims(answer, _CANCEL_CLAIM)
    if cancelled and not any(c.ok for c in evidence.cancellations):
        return Verdict("booking", False, "answer says a session was cancelled but no cancel_booking succeeded",
                       "replan", {"claims": cancelled})
    claims = _booking_claims(answer)
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


# The assistant's own internals: tool names and the tag around the student's words. A reply naming them is
# describing how it works inside, which is what a prompt-extraction attack is after.
_INTERNALS = re.compile(
    r"\b(?:search_knowledge|score_lead|upsert_lead|get_lead|get_slots|get_counsellors|book_slot|cancel_booking|"
    r"send_message|schedule_followup|request_fee_waiver|request_booking_override|request_bulk_message|"
    r"student_message|system\s+prompt|enforced\s+by\s+code)\b", re.IGNORECASE)
# Off-topic work an admissions assistant never produces: program code.
_CODE = re.compile(r"```|^\s*(?:def|class|import|from\s+\S+\s+import|function|public\s+static|#include)\b",
                   re.IGNORECASE | re.MULTILINE)
_WORD = re.compile(r"\w+")
LEAK_WINDOW = 8          # this many consecutive words of the instructions in a reply count as a leak


def _leaks(answer: str, protected: str) -> bool:
    if not protected:
        return False
    words = _WORD.findall(protected.lower())
    text = " ".join(_WORD.findall(answer.lower()))
    return any(" ".join(words[i:i + LEAK_WINDOW]) in text for i in range(len(words) - LEAK_WINDOW + 1))


def check_scope(answer: str, protected: str = "") -> Verdict:
    """Any intent: the reply must not reveal the assistant's instructions or tools, or write program code.

    A failure is refused with a fixed message, not rewritten: there is nothing in such a reply to keep.
    """
    if _leaks(answer, protected):
        return Verdict("scope", False, "answer repeats the assistant's own instructions", "refuse")
    unbracketed = re.sub(r"\[\s*[a-z_]+\s*\]", " ", answer)     # a "[tool_name]" citation is stripped before sending
    named = sorted({m.group(0).lower() for m in _INTERNALS.finditer(unbracketed)})
    if named:
        return Verdict("scope", False, "answer names the assistant's internal tools", "refuse", {"named": named})
    if _CODE.search(answer):
        return Verdict("scope", False, "answer contains program code, which is outside admissions", "refuse")
    return Verdict("scope", True, "within admissions")


def verify_answer(answer: str, evidence: TurnEvidence, intent: str, question: str = "",
                  known_text: str = "", approved_actions: Optional[set[str]] = None,
                  protected: str = "") -> list[Verdict]:
    """Run every verifier; the loop acts on the first failure. `protected` is text a reply must never repeat."""
    return [check_scope(answer, protected), check_grounding(answer, evidence, intent, question),
            check_booking(answer, evidence), check_no_false_grant(answer, approved_actions),
            check_figures(answer, evidence, known_text or question)]
