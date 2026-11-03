"""Agent loop: PLAN -> ACT -> VERIFY -> (RETRY | REPLAN) -> RESPOND.

`AgentLoop.run` is a generator of SSE-shaped events (SPEC 2.2). It never
raises: every failure path ends in a polite message and a `final` event.
The drafted answer is held back until the verifiers pass, then streamed as
`message` chunks, so the student never sees an unverified fact.
"""
from __future__ import annotations

import concurrent.futures
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Generator, Iterator

from app.agent import tools_schema
from app.agent.llm import LLM, ToolCall
from app.agent.prompts import INTENTS, PLAN_PROMPT, SYSTEM_PROMPT
from app.agent.verify import NOT_IN_KB, TurnEvidence, citations, verify_answer
from app.contracts import tools
from app.contracts.models import BookingResult, KnowledgeResult

MAX_TOOL_STEPS = 8
MAX_REPLANS = 1
MAX_RETRIES = 2
BACKOFF_SECONDS = (0.5, 1.5)
TOOL_TIMEOUT_SECONDS = 15
CHUNK_CHARS = 40

ESCALATED_MSG = ("I don't have verified information on that, so I won't guess. "
                 "I've passed your question to an admissions counsellor, who will get back to you.")
ESCALATION_FAILED_MSG = ("I don't have verified information on that, so I won't guess. "
                         "Please ask to speak with an admissions counsellor and they will help you.")
SENSITIVE_NOTE = ("\n\nI can't approve waivers or exceptions myself, so I've also passed this to an "
                  "admissions counsellor in case your situation qualifies.")
FALLBACK_MSG = ("Sorry, I couldn't complete that right now. An admissions counsellor can help you; "
                "would you like a callback?")


@dataclass
class TurnContext:
    """Everything the loop needs about the current chat turn."""

    message: str
    lead_id: int
    session_id: str
    channel: str = "web"
    history: list[dict] = field(default_factory=list)   # [{"role": "student"|"agent", "text": str}]
    lead_profile: dict = field(default_factory=dict)


Events = Generator[dict, None, Any]


class AgentLoop:
    def __init__(self, llm: LLM, sleep: Callable[[float], None] = time.sleep):
        self.llm = llm
        self.sleep = sleep
        self.step = 0

    # ----- public -------------------------------------------------------
    def run(self, ctx: TurnContext) -> Iterator[dict]:
        """Yield events for one turn. Always ends with a `final` event."""
        self.step = 0
        try:
            yield from self._turn(ctx)
        except Exception as exc:  # last-resort guard: the chat must never crash
            yield self._event("error", {"error": type(exc).__name__, "detail": str(exc)[:300]})
            yield from self._respond(FALLBACK_MSG, intent="unknown", escalation=None)

    # ----- phases -------------------------------------------------------
    def _turn(self, ctx: TurnContext) -> Events:
        context = self._context_block(ctx)
        plan = yield from self._plan(context)
        intent = plan["intent"]
        yield self._event("plan", {**plan, "session_id": ctx.session_id, "lead_id": ctx.lead_id})

        evidence = TurnEvidence()
        convo = self.llm.start(context)
        replans = 0
        draft = ""
        while True:
            result = yield from self._retry("llm.act", lambda: self.llm.act(
                convo, SYSTEM_PROMPT, tools_schema.DECLARATIONS))
            if result is None:
                yield from self._respond(FALLBACK_MSG, intent, escalation=None)
                return

            if result.calls:
                for call in result.calls:
                    if self.step >= MAX_TOOL_STEPS:
                        yield self._event("error", {"error": "step_limit", "limit": MAX_TOOL_STEPS})
                        yield from self._respond(FALLBACK_MSG, intent, escalation=None)
                        return
                    yield from self._run_tool(call, ctx, convo, evidence)
                continue

            draft = result.text.strip()
            failed = None
            for verdict in verify_answer(draft, evidence, intent, ctx.message):
                yield self._event("verify", verdict.as_event())
                if not verdict.ok and failed is None:
                    failed = verdict
            if failed is None:
                break
            if failed.action == "replan" and replans < MAX_REPLANS:
                replans += 1
                self.llm.add_feedback(convo, self._feedback(failed))
                continue
            approval = yield from self._escalate(ctx, failed.reason)
            yield from self._respond(ESCALATED_MSG if approval else ESCALATION_FAILED_MSG, intent, approval)
            return

        if not draft:
            yield from self._respond(FALLBACK_MSG, intent, escalation=None)
            return
        approval = None
        if intent == "sensitive_request":
            approval = yield from self._escalate(ctx, "sensitive request: counsellor decision needed")
            if approval:
                draft += SENSITIVE_NOTE
        yield from self._respond(draft, intent, approval)

    def _plan(self, context: str) -> Events:
        prompt = PLAN_PROMPT.format(intents=INTENTS, tools=tools_schema.TOOL_NAMES, context=context)
        raw = yield from self._retry("llm.plan", lambda: self.llm.plan(SYSTEM_PROMPT, prompt))
        raw = raw if isinstance(raw, dict) else {}
        intent = raw.get("intent") if raw.get("intent") in INTENTS else "unknown"
        steps = [s for s in raw.get("steps", []) if isinstance(s, dict)][:MAX_TOOL_STEPS]
        return {"intent": intent, "steps": steps}

    def _run_tool(self, call: ToolCall, ctx: TurnContext, convo, evidence: TurnEvidence) -> Events:
        self.step += 1
        yield self._event("tool_call", {"id": call.id, "name": call.name, "args": call.args})
        if call.name not in tools_schema.TOOL_NAMES:
            result, error = None, f"unknown tool {call.name}"
        else:
            result = yield from self._retry(
                call.name, lambda: self._with_timeout(tools_schema.execute, call.name, call.args, ctx.lead_id))
            error = None if result is not None else "tool failed after retries"

        payload = tools_schema.to_jsonable(result) if error is None else {"error": error}
        self.llm.add_tool_result(convo, call, payload, is_error=error is not None)
        yield self._event("tool_result", {"id": call.id, "name": call.name, "ok": error is None,
                                          "result": payload})
        if isinstance(result, KnowledgeResult):
            evidence.knowledge.append(result)
        elif isinstance(result, BookingResult):
            evidence.bookings.append(result)

    def _escalate(self, ctx: TurnContext, reason: str) -> Events:
        payload = {"lead_id": ctx.lead_id, "session_id": ctx.session_id,
                   "question": ctx.message, "reason": reason}
        approval = yield from self._retry("request_approval",
                                          lambda: tools.request_approval("escalate_question", payload))
        yield self._event("escalation", {
            "reason": reason, "recorded": approval is not None,
            "approval_id": approval.approval_id if approval else None,
            "status": approval.status if approval else None,
        })
        return approval

    def _respond(self, text: str, intent: str, escalation) -> Events:
        for i in range(0, len(text), CHUNK_CHARS):
            yield self._event("message", {"delta": text[i:i + CHUNK_CHARS]})
        yield self._event("final", {
            "text": text, "intent": intent, "citations": citations(text),
            "escalated": escalation is not None,
            "approval_id": escalation.approval_id if escalation else None,
        })

    # ----- helpers ------------------------------------------------------
    def _retry(self, label: str, fn: Callable[[], Any]) -> Events:
        """Call fn with up to MAX_RETRIES retries and backoff. Returns None if all attempts fail."""
        for attempt in range(MAX_RETRIES + 1):
            try:
                return fn()
            except Exception as exc:
                if attempt == MAX_RETRIES:
                    yield self._event("error", {"error": "retries_exhausted", "target": label,
                                                "detail": f"{type(exc).__name__}: {exc}"[:300]})
                    return None
                yield self._event("retry", {"target": label, "attempt": attempt + 1,
                                            "error": f"{type(exc).__name__}: {exc}"[:300]})
                self.sleep(BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)])

    @staticmethod
    def _with_timeout(fn, *args):
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            return pool.submit(fn, *args).result(timeout=TOOL_TIMEOUT_SECONDS)
        finally:
            pool.shutdown(wait=False)

    @staticmethod
    def _feedback(verdict) -> str:
        return (f"VERIFIER REJECTED your draft: {verdict.reason} {verdict.details or ''}. "
                "Rewrite it using only facts from the search_knowledge results, citing each as [source] "
                f"and copying numbers exactly, or reply with {NOT_IN_KB} if the results do not answer it.")

    @staticmethod
    def _context_block(ctx: TurnContext) -> str:
        known = {k: v for k, v in ctx.lead_profile.items() if v not in (None, "", False)}
        lines = [f"Channel: {ctx.channel}", f"Known student profile: {known or 'nothing yet'}"]
        if ctx.history:
            lines.append("Conversation so far:")
            lines += [f"{'Student' if h['role'] == 'student' else 'Assistant'}: {h['text']}"
                      for h in ctx.history]
        lines.append(f"Student's new message: {ctx.message}")
        return "\n".join(lines)

    def _event(self, type_: str, data: dict) -> dict:
        return {"type": type_, "step": self.step, "ts": datetime.now(timezone.utc).isoformat(), "data": data}
