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
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Generator, Iterator, Optional

from app.agent import guards, tools_schema
from app.agent.llm import LLM, ToolCall
from app.agent.prompts import INTENTS, PLAN_PROMPT, SYSTEM_PROMPT
from app.agent.tools_schema import ToolEnv
from app.agent.verify import NOT_IN_KB, citations, verify_answer
from app.contracts import tools
from app.contracts.models import ApprovalRequest, BookingResult, KnowledgeResult, Lead, LeadScore, Slot

MAX_TOOL_STEPS = 8
MAX_REPLANS = 1
MAX_RETRIES = 2
BACKOFF_SECONDS = (0.5, 1.5)
TOOL_TIMEOUT_SECONDS = 15
LLM_TIMEOUT_SECONDS = 40       # hard wall-clock cap per model call, whatever the SDK does
TURN_BUDGET_SECONDS = 90       # no new retries once a turn has used this much time
CHUNK_CHARS = 40
OBJECTIONS = {"fees", "distance"}

ESCALATED_MSG = ("I don't have verified information on that, so I won't guess. "
                 "I've passed your question to an admissions counsellor, who will get back to you.")
ESCALATION_FAILED_MSG = ("I don't have verified information on that, so I won't guess. "
                         "Please ask to speak with an admissions counsellor and they will help you.")
SENSITIVE_NOTE = ("\n\nI can't approve waivers or exceptions myself, so I've also passed this to an "
                  "admissions counsellor in case your situation qualifies.")
PENDING_NOTE = "\n\nYour request is pending counsellor approval. Nothing has been applied yet."
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
    lead_score: Optional[LeadScore] = None
    requests: list[dict] = field(default_factory=list)  # this lead's approval requests and their status
    role: str = "anonymous"
    now_ist: str = ""                                    # virtual clock, for dates in tool calls


Events = Generator[dict, None, Any]


class AgentLoop:
    def __init__(self, llm: LLM, sleep: Callable[[float], None] = time.sleep):
        self.llm = llm
        self.sleep = sleep
        self.step = 0
        self.deadline = float("inf")

    # ----- public -------------------------------------------------------
    def run(self, ctx: TurnContext) -> Iterator[dict]:
        """Yield events for one turn. Always ends with a `final` event."""
        self.step = 0
        self.deadline = time.monotonic() + TURN_BUDGET_SECONDS
        try:
            yield from self._turn(ctx)
        except Exception as exc:  # last-resort guard: the chat must never crash
            yield self._event("error", {"error": type(exc).__name__, "detail": str(exc)[:300]})
            yield from self._respond(ctx, FALLBACK_MSG, "unknown", None, None)

    # ----- phases -------------------------------------------------------
    def _turn(self, ctx: TurnContext) -> Events:
        guard = guards.check_message(ctx.message)
        if guard == "injection":
            yield from self._refuse_injection(ctx)
            return
        if guard == "opt_out":
            yield from self._opt_out(ctx)
            return

        context = self._context_block(ctx)
        plan = yield from self._plan(context)
        intent = plan["intent"]
        yield self._event("plan", {**plan, "session_id": ctx.session_id, "lead_id": ctx.lead_id})

        env = ToolEnv(lead_id=ctx.lead_id, role=ctx.role, session_id=ctx.session_id)
        already_approved = any(r["status"] == "approved" for r in ctx.requests)
        convo = self.llm.start(context)
        replans = 0
        while True:
            result = yield from self._retry("llm.act", lambda: self._with_timeout(
                self.llm.act, convo, SYSTEM_PROMPT, tools_schema.DECLARATIONS, seconds=LLM_TIMEOUT_SECONDS))
            if result is None:
                yield from self._respond(ctx, FALLBACK_MSG, intent, env.evidence.escalation, env)
                return

            if result.calls:
                for call in result.calls:
                    if self.step >= MAX_TOOL_STEPS:
                        yield self._event("error", {"error": "step_limit", "limit": MAX_TOOL_STEPS})
                        yield from self._respond(ctx, FALLBACK_MSG, intent, env.evidence.escalation, env)
                        return
                    yield from self._run_tool(call, ctx, convo, env)
                yield from self._auto_score(ctx, convo, env)
                continue

            draft = result.text.strip()
            failed = None
            for verdict in verify_answer(draft, env.evidence, intent, ctx.message, context, already_approved):
                yield self._event("verify", verdict.as_event())
                if not verdict.ok and failed is None:
                    failed = verdict
            if failed is None:
                break
            if failed.action == "replan" and replans < MAX_REPLANS:
                replans += 1
                self.llm.add_feedback(convo, self._feedback(failed))
                continue
            approval = env.evidence.escalation or (yield from self._escalate(ctx, failed.reason))
            yield from self._respond(ctx, ESCALATED_MSG if approval else ESCALATION_FAILED_MSG, intent, approval, env)
            return

        if not draft:
            yield from self._respond(ctx, FALLBACK_MSG, intent, env.evidence.escalation, env)
            return
        yield from self._finish(ctx, draft, intent, plan.get("objection"), env)

    def _finish(self, ctx: TurnContext, draft: str, intent: str, objection: Optional[str], env: ToolEnv) -> Events:
        """A verified answer: settle any approval wording, plan the next follow-up, then respond."""
        evidence = env.evidence
        approval = evidence.escalation
        if evidence.approvals:
            if "pending" not in draft.lower():
                draft += PENDING_NOTE
        elif intent == "sensitive_request" and approval is None:
            approval = yield from self._escalate(ctx, "sensitive request: counsellor decision needed")
            if approval:
                draft += SENSITIVE_NOTE
        yield from self._plan_followup(ctx, objection)
        yield from self._respond(ctx, draft, intent, approval, env)

    def _plan(self, context: str) -> Events:
        prompt = PLAN_PROMPT.format(intents=INTENTS, tools=tools_schema.TOOL_NAMES, context=context)
        raw = yield from self._retry("llm.plan", lambda: self._with_timeout(
            self.llm.plan, SYSTEM_PROMPT, prompt, seconds=LLM_TIMEOUT_SECONDS))
        raw = raw if isinstance(raw, dict) else {}
        intent = raw.get("intent") if raw.get("intent") in INTENTS else "unknown"
        steps = [s for s in raw.get("steps", []) if isinstance(s, dict)][:MAX_TOOL_STEPS]
        objection = raw.get("objection") if raw.get("objection") in OBJECTIONS else None
        return {"intent": intent, "steps": steps, "objection": objection}

    # ----- checks that need no model call -------------------------------
    def _refuse_injection(self, ctx: TurnContext) -> Events:
        yield self._event("plan", {"intent": "sensitive_request", "guard": "injection", "session_id": ctx.session_id,
                                   "lead_id": ctx.lead_id, "steps": [{"goal": "Refuse without calling the model",
                                                                      "tool": None}]})
        yield self._event("verify", {"check": "injection", "ok": False, "action": "refuse",
                                     "reason": "message tries to change the rules or the assistant's role"})
        yield from self._respond(ctx, guards.INJECTION_MSG, "sensitive_request", None, None)

    def _opt_out(self, ctx: TurnContext) -> Events:
        yield self._event("plan", {"intent": "followup_reply", "guard": "opt_out", "session_id": ctx.session_id,
                                   "lead_id": ctx.lead_id, "steps": [{"goal": "Opt the student out now",
                                                                      "tool": "opt_out"}]})
        self.step += 1
        yield self._event("tool_call", {"id": "guard-opt-out", "name": "opt_out", "args": {}, "by": "code"})
        result = yield from self._retry("opt_out", lambda: self._with_timeout(tools.opt_out_lead, ctx.lead_id))
        yield self._event("tool_result", {"id": "guard-opt-out", "name": "opt_out", "ok": result is not None,
                                          "result": {"opted_out": result is not None}})
        yield from self._respond(ctx, guards.OPT_OUT_MSG if result else FALLBACK_MSG, "followup_reply", None, None)

    # ----- tools --------------------------------------------------------
    def _run_tool(self, call: ToolCall, ctx: TurnContext, convo, env: ToolEnv) -> Events:
        self.step += 1
        yield self._event("tool_call", {"id": call.id, "name": call.name, "args": call.args})
        if call.name not in tools_schema.TOOL_NAMES:
            result, error = None, f"unknown tool {call.name}"
        else:
            result = yield from self._retry(
                call.name, lambda: self._with_timeout(tools_schema.execute, call.name, call.args, env))
            error = None if result is not None else "tool failed after retries"

        payload = tools_schema.to_jsonable(result) if error is None else {"error": error}
        if error and call.name == "book_slot":
            payload.update((yield from self._booking_fallback(ctx, env)))
        self.llm.add_tool_result(convo, call, payload, is_error=error is not None)
        yield self._event("tool_result", {"id": call.id, "name": call.name, "ok": error is None, "result": payload})
        yield from self._record(call, result, env)

    def _record(self, call: ToolCall, result: Any, env: ToolEnv) -> Events:
        evidence = env.evidence
        if isinstance(result, KnowledgeResult):
            evidence.knowledge.append(result)
        elif isinstance(result, BookingResult):
            evidence.bookings.append(result)
            evidence.tool_text.append(str(result.model_dump()))
        elif isinstance(result, list) and result and isinstance(result[0], Slot):
            evidence.tool_text.append(str(tools_schema.to_jsonable(result)))
        elif isinstance(result, LeadScore):
            evidence.score = result
        elif isinstance(result, Lead) and call.name == "upsert_lead":
            evidence.profile = result.profile.model_dump(exclude={"channel"})
        elif isinstance(result, ApprovalRequest):
            evidence.approvals.append(result)
            yield self._event("approval_pending", {"approval_id": result.approval_id, "action": result.action,
                                                   "status": result.status})

    def _booking_fallback(self, ctx: TurnContext, env: ToolEnv) -> Events:
        """The calendar failed after retries: find other slots, or arrange a human callback."""
        today = (ctx.now_ist or datetime.now(timezone.utc).isoformat())[:10]
        until = (date.fromisoformat(today) + timedelta(days=7)).isoformat()
        slots = yield from self._retry("get_slots", lambda: self._with_timeout(tools.get_slots, today, until))
        if slots:
            alternatives = tools_schema.to_jsonable(slots[:3])
            env.evidence.tool_text.append(str(alternatives))
            return {"fallback": "other_slots_available", "alternatives": alternatives}
        env.evidence.escalation = yield from self._escalate(ctx, "calendar unavailable: booking failed after retries")
        return {"fallback": "counsellor_callback"}

    def _auto_score(self, ctx: TurnContext, convo, env: ToolEnv) -> Events:
        """Once the required details are complete, code scores the lead even if the model forgot to."""
        evidence = env.evidence
        if evidence.score is not None or evidence.profile is None or tools_schema.missing_fields(evidence.profile):
            return
        self.step += 1
        yield self._event("tool_call", {"id": "auto-score", "name": "score_lead", "args": {}, "by": "code"})
        score = yield from self._retry("score_lead", lambda: self._with_timeout(tools_schema.score_and_save, ctx.lead_id))
        yield self._event("tool_result", {"id": "auto-score", "name": "score_lead", "ok": score is not None,
                                          "result": tools_schema.to_jsonable(score) if score else None})
        if score is not None:
            evidence.score = score
            self.llm.add_feedback(convo, "System note: the student's profile is complete and their lead score has "
                                         "been saved. Do not mention the score. Finish your reply to the student.")

    def _plan_followup(self, ctx: TurnContext, objection: Optional[str]) -> Events:
        """Policy in code (SPEC 2.5). A failure here must not cost the student their answer."""
        result = yield from self._retry("plan_followup", lambda: self._with_timeout(
            tools.plan_followup, ctx.lead_id, objection))
        if result and result.get("planned"):
            yield self._event("tool_call", {"id": "plan-followup", "name": "plan_followup",
                                            "args": {"objection": objection}, "by": "code"})
            yield self._event("tool_result", {"id": "plan-followup", "name": "plan_followup", "ok": True,
                                              "result": result["planned"]})

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

    def _respond(self, ctx: TurnContext, text: str, intent: str, escalation, env: Optional[ToolEnv]) -> Events:
        evidence = env.evidence if env else None
        approval = escalation or (evidence.approvals[0] if evidence and evidence.approvals else None)
        profile = (evidence.profile if evidence else None) or ctx.lead_profile
        score = (evidence.score if evidence else None) or ctx.lead_score
        for i in range(0, len(text), CHUNK_CHARS):
            yield self._event("message", {"delta": text[i:i + CHUNK_CHARS]})
        yield self._event("final", {
            "text": text, "intent": intent, "citations": citations(text),
            "escalated": escalation is not None,
            "approval_id": approval.approval_id if approval else None,
            "approval_status": approval.status if approval else None,
            "missing_fields": tools_schema.missing_fields(profile),
            "lead_score": score.model_dump() if score else None,
        })

    # ----- helpers ------------------------------------------------------
    def _retry(self, label: str, fn: Callable[[], Any]) -> Events:
        """Call fn with up to MAX_RETRIES retries and backoff. Returns None if all attempts fail."""
        for attempt in range(MAX_RETRIES + 1):
            try:
                return fn()
            except Exception as exc:
                if attempt == MAX_RETRIES or time.monotonic() >= self.deadline:
                    yield self._event("error", {"error": "retries_exhausted", "target": label,
                                                "detail": f"{type(exc).__name__}: {exc}"[:300]})
                    return None
                yield self._event("retry", {"target": label, "attempt": attempt + 1,
                                            "error": f"{type(exc).__name__}: {exc}"[:300]})
                self.sleep(BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)])

    @staticmethod
    def _with_timeout(fn, *args, seconds: float = TOOL_TIMEOUT_SECONDS):
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            return pool.submit(fn, *args).result(timeout=seconds)
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
        lines = [f"Current date and time (IST): {ctx.now_ist or 'unknown'}",
                 f"Channel: {ctx.channel}", f"Known student profile: {known or 'nothing yet'}"]
        missing = tools_schema.missing_fields(ctx.lead_profile)
        if missing:
            lines.append(f"Details still missing for qualification: {', '.join(missing)}")
        if ctx.requests:
            lines.append("This student's requests: " + "; ".join(f"{r['action']}: {r['status']}" for r in ctx.requests))
        if ctx.history:
            lines.append("Conversation so far:")
            lines += [f"{'Student' if h['role'] == 'student' else 'Assistant'}: {h['text']}"
                      for h in ctx.history]
        message = ctx.message.replace("<", "(").replace(">", ")")     # the student can't close the tag
        lines.append(f"<student_message>{message}</student_message>")
        return "\n".join(lines)

    def _event(self, type_: str, data: dict) -> dict:
        return {"type": type_, "step": self.step, "ts": datetime.now(timezone.utc).isoformat(), "data": data}
