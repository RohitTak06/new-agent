"""Unit and benchmark tests for Knowledge and Lead Intelligence."""
import pytest

from app.contracts.models import LeadProfile
from app.contracts import tools
from app.intel.service import search_knowledge, score_lead
from app.intel.test_set import run_benchmark_evaluation


def test_knowledge_search_in_scope():
    res = search_knowledge("What is the B.Tech CSE tuition fee?")
    assert res.answer_found is True
    assert len(res.chunks) > 0
    assert any("programs_and_fees.md" in c.source for c in res.chunks)


def test_knowledge_search_scholarship_continuation():
    res = search_knowledge("What is the minimum CGPA required to retain scholarship in 2nd year?")
    assert res.answer_found is True
    assert len(res.chunks) > 0
    assert any("scholarships.md" in c.source for c in res.chunks)


def test_knowledge_search_out_of_scope_guard():
    # Hallucination trap questions MUST return answer_found=False
    traps = [
        "Do you have MBBS or medical college admissions?",
        "Will I get a free laptop upon joining?",
        "Is there a guaranteed research internship at NASA?",
        "What is the commercial pilot aviation training fee?"
    ]
    for q in traps:
        res = search_knowledge(q)
        assert res.answer_found is False, f"Expected answer_found=False for '{q}', got {res}"
        assert len(res.chunks) == 0


def test_lead_scoring_hot():
    profile = LeadProfile(
        name="Aarav Sharma",
        phone="9876543210",
        email="aarav@gmail.com",
        city="Jaipur",
        program_interest="B.Tech CSE",
        twelfth_percent=94.5,
        entrance_exam="JEE Mains: 92.5 percentile",
        budget_lakh=11.0,
        asked_scholarship=True
    )
    score = score_lead(profile)
    assert score.tier == "hot"
    assert score.score >= 75
    assert len(score.reasons) > 0


def test_lead_scoring_cold():
    profile = LeadProfile(
        name="Anonymous Visitor",
        channel="web"
    )
    score = score_lead(profile)
    assert score.tier == "cold"
    assert score.score < 50


def test_tool_contract_switch(monkeypatch):
    monkeypatch.setenv("USE_REAL_INTEL", "1")
    res = tools.search_knowledge("B.Tech scholarship 95 percentile")
    assert res.answer_found is True
    assert len(res.chunks) > 0

    monkeypatch.setenv("USE_REAL_INTEL", "0")
    stub_res = tools.search_knowledge("B.Tech scholarship")
    assert "stub" in stub_res.chunks[0].source


def test_full_benchmark_accuracy():
    report = run_benchmark_evaluation()
    assert report["accuracy_percent"] >= 95.0
    assert report["zero_hallucination_guard_accuracy_percent"] == 100.0


if __name__ == "__main__":
    print("Running tests manually...")
    test_knowledge_search_in_scope()
    test_knowledge_search_scholarship_continuation()
    test_knowledge_search_out_of_scope_guard()
    test_lead_scoring_hot()
    test_lead_scoring_cold()
    test_tool_contract_switch()
    test_full_benchmark_accuracy()
    print("All intel unit tests passed successfully!")
