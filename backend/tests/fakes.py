"""Scripted stand-in for GeminiLLM so agent tests are deterministic and offline."""
from __future__ import annotations

from typing import Any

from app.agent.llm import ActResult, Conversation, ToolCall


def calls(*specs: tuple[str, dict]) -> ActResult:
    """ActResult asking for tool calls, e.g. calls(("search_knowledge", {"query": "fees"}))."""
    return ActResult(text="", calls=[ToolCall(id=f"c{i}", name=n, args=a) for i, (n, a) in enumerate(specs)])


def says(text: str) -> ActResult:
    return ActResult(text=text)


class FakeLLM:
    """Returns `plan` from plan() and pops one scripted item per act() call.

    Script items are ActResult, an Exception to raise, or a callable(convo) -> ActResult.
    When the script runs out it keeps repeating the last item.
    """

    def __init__(self, plan: dict | Exception, script: list[Any]):
        self._plan = plan
        self.script = list(script)
        self.tool_results: list[tuple[str, Any, bool]] = []
        self.feedback: list[str] = []
        self.act_calls = 0

    def plan(self, system: str, prompt: str) -> dict:
        if isinstance(self._plan, Exception):
            raise self._plan
        return self._plan

    def start(self, user_text: str) -> Conversation:
        return Conversation(steps=[{"type": "user_input", "text": user_text}])

    def act(self, convo: Conversation, system: str, tools: list[dict]) -> ActResult:
        self.act_calls += 1
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item(convo) if callable(item) else item

    def add_tool_result(self, convo: Conversation, call: ToolCall, result: Any, is_error: bool = False) -> None:
        self.tool_results.append((call.name, result, is_error))

    def add_feedback(self, convo: Conversation, text: str) -> None:
        self.feedback.append(text)
