"""Optional smoke test against real Gemini. Skipped by default; spends about 6-8 requests.

    pytest -m live
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.agent import router as agent_router
from app.agent.llm import GeminiLLM
from app.main import app
from conftest import LIVE_LLM

pytestmark = pytest.mark.live


def _chat(client, message):
    res = client.post("/agent/chat", json={"message": message})
    return [json.loads(line[6:]) for line in res.text.splitlines() if line.startswith("data: ")]


@pytest.fixture
def client(monkeypatch):
    if not LIVE_LLM["LLM_API_KEY"] or not LIVE_LLM["LLM_MODEL"]:
        pytest.skip("LLM_API_KEY and LLM_MODEL are not set")
    llm = GeminiLLM(api_key=LIVE_LLM["LLM_API_KEY"], model=LIVE_LLM["LLM_MODEL"])
    monkeypatch.setattr(agent_router, "get_llm", lambda: llm)
    return TestClient(app)


def test_live_fee_answer_is_cited_and_every_check_passes(client):
    events = _chat(client, "What is the annual academic fee for B.Tech?")
    final = events[-1]["data"]
    assert final["citations"], final["text"]
    assert "3,40,000" in final["text"] or "340000" in final["text"]
    assert all(e["data"]["ok"] for e in events if e["type"] == "verify")


def test_live_waiver_request_stays_pending(client):
    events = _chat(client, "My family can't afford this. Please waive my fees.")
    final = events[-1]["data"]
    assert final["approval_id"] is not None and "approved" not in final["text"].lower().replace("not approved", "")
