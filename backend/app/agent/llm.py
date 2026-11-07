"""Thin Gemini client over the google-genai Interactions API (stateless, store=False).

The agent loop only sees the small `LLM` protocol below, so tests swap in a
scripted fake and no SDK detail leaks out of this file. History lives in our
DB; each turn sends the full step list and returns model steps verbatim
(thought signatures must be sent back exactly as received).
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger("app.agent.llm")

TIMEOUT_WITH_FALLBACK_SECONDS = 18.0   # two tries must fit inside the agent loop's 40-second cap per model call
PRIMARY_COOLDOWN_SECONDS = 60.0        # after a failure, don't spend every call rediscovering it
_TRANSIENT_STATUS = {429, 500, 502, 503, 504}
_TRANSIENT_ERRORS = {"APITimeoutError", "APIConnectionError", "TimeoutError"}


def is_transient(exc: Exception) -> bool:
    """Would the same request be worth sending to another model? A bad request would just fail again."""
    return type(exc).__name__ in _TRANSIENT_ERRORS or getattr(exc, "status_code", None) in _TRANSIENT_STATUS


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass
class ActResult:
    text: str
    calls: list[ToolCall] = field(default_factory=list)


@dataclass
class Conversation:
    """Opaque per-turn state owned by the LLM implementation."""

    steps: list[dict] = field(default_factory=list)


class LLM(Protocol):
    def plan(self, system: str, prompt: str) -> dict: ...
    def write(self, system: str, prompt: str) -> str: ...
    def start(self, user_text: str) -> Conversation: ...
    def act(self, convo: Conversation, system: str, tools: list[dict]) -> ActResult: ...
    def add_tool_result(self, convo: Conversation, call: ToolCall, result: Any, is_error: bool = False) -> None: ...
    def add_feedback(self, convo: Conversation, text: str) -> None: ...


class LLMConfigError(RuntimeError):
    """LLM_API_KEY or LLM_MODEL missing."""


def _user_step(text: str) -> dict:
    return {"type": "user_input", "content": [{"type": "text", "text": text}]}


def parse_json(text: str) -> dict:
    """Parse a JSON object, tolerating ```json fences around it."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`").removeprefix("json").strip()
    return json.loads(t)


class GeminiLLM:
    """Gemini via `client.interactions.create`. Reads LLM_API_KEY, LLM_MODEL and, optionally, LLM_FALLBACK_MODEL.

    With a fallback set, an overloaded or slow model doesn't fail the call: the other one is
    tried, and stays first for a while. Google's load varies by model and by hour.
    """

    _OUTPUT_STEPS = {"thought", "model_output", "function_call"}

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 30.0,
                 fallback_model: str | None = None):
        from google import genai
        from google.genai import types

        api_key = api_key or os.getenv("LLM_API_KEY")
        self.model = model or os.getenv("LLM_MODEL")
        if not api_key or not self.model:
            raise LLMConfigError("Set LLM_API_KEY and LLM_MODEL in .env")
        self.fallback_model = fallback_model or os.getenv("LLM_FALLBACK_MODEL") or None
        if self.fallback_model:
            timeout = min(timeout, TIMEOUT_WITH_FALLBACK_SECONDS)
        self._primary_down_until = 0.0
        # The SDK honours Retry-After before retrying; for a quota 429 that is hours. So it may
        # retry once, only on transient 5xx; a 429 fails at once and the agent loop handles it
        # with its own visible retries (`retry` events) under a hard per-turn time budget.
        self.client = genai.Client(api_key=api_key, http_options=types.HttpOptions(
            timeout=int(timeout * 1000),
            retry_options=types.HttpRetryOptions(attempts=1, http_status_codes=[500, 502, 503, 504])))
        self.timeout = timeout

    def _call(self, model: str, kwargs: dict) -> Any:
        """One request, limited by the clock: the SDK's timeout only covers gaps between bytes."""
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = pool.submit(self.client.interactions.create, model=model, store=False,
                                 timeout=self.timeout, **kwargs)
            try:
                return future.result(timeout=self.timeout)
            except concurrent.futures.TimeoutError:
                raise TimeoutError(f"{model} took longer than {self.timeout:.0f}s") from None
        finally:
            pool.shutdown(wait=False)

    def _models(self) -> list[str]:
        if not self.fallback_model:
            return [self.model]
        if time.monotonic() < self._primary_down_until:
            return [self.fallback_model, self.model]
        return [self.model, self.fallback_model]

    def _create(self, **kwargs: Any) -> Any:
        models = self._models()
        for model in models[:-1]:
            try:
                return self._call(model, kwargs)
            except Exception as exc:
                if not is_transient(exc):
                    raise
                logger.warning("%s failed (%s); trying the other model", model, type(exc).__name__)
                # The model that just failed goes last for a while, whichever it was.
                self._primary_down_until = time.monotonic() + PRIMARY_COOLDOWN_SECONDS if model == self.model else 0.0
        return self._call(models[-1], kwargs)

    def plan(self, system: str, prompt: str) -> dict:
        interaction = self._create(
            input=prompt,
            system_instruction=system,
            response_format={"type": "text", "mime_type": "application/json"},
        )
        return parse_json(interaction.output_text or "{}")

    def write(self, system: str, prompt: str) -> str:
        """One-shot text generation, with no tools."""
        interaction = self._create(input=prompt, system_instruction=system)
        return interaction.output_text or ""

    def start(self, user_text: str) -> Conversation:
        return Conversation(steps=[_user_step(user_text)])

    def act(self, convo: Conversation, system: str, tools: list[dict]) -> ActResult:
        interaction = self._create(input=convo.steps, system_instruction=system, tools=tools)
        out = [s for s in (interaction.steps or []) if s.type in self._OUTPUT_STEPS]
        convo.steps.extend(s.model_dump(mode="json", by_alias=True, exclude_none=True) for s in out)
        calls = [ToolCall(id=s.id, name=s.name, args=dict(s.arguments or {}))
                 for s in out if s.type == "function_call"]
        return ActResult(text=(interaction.output_text or "") if not calls else "", calls=calls)

    def add_tool_result(self, convo: Conversation, call: ToolCall, result: Any, is_error: bool = False) -> None:
        convo.steps.append({
            "type": "function_result", "call_id": call.id, "name": call.name,
            "result": json.dumps(result, default=str), "is_error": is_error,
        })

    def add_feedback(self, convo: Conversation, text: str) -> None:
        convo.steps.append(_user_step(text))
