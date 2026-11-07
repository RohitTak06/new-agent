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


def test_every_knowledge_section_names_its_programme_when_it_is_programme_specific():
    """Chunks are retrieved alone, so a heading like "Class XII Merit" gets read as applying to any programme."""
    from app.intel.retrieval import store
    for _text, source in store.raw_chunks:
        anchor = source.split("#")[-1]
        if "merit" in anchor or "portfolio" in anchor or "entrance-exams-nid" in anchor:
            assert anchor.startswith("b-des") or anchor.startswith("b-tech"), source


def test_official_fees_are_in_the_knowledge_base():
    """Figures from jklu.edu.in/admissions/fee-structure, and old figures that were wrong."""
    from app.intel.retrieval import store
    text = " ".join(t for t, _ in store.raw_chunks)
    for figure in ("3,40,000", "4,03,000", "1,98,000", "3,50,000", "1,80,000", "3,10,000", "54,500", "65,500", "1,38,000"):
        assert figure in text, figure
    for stale in ("2,65,000", "2,90,000", "1,60,000", "10,85,000", "22.5 LPA", "JKLU-EET", "1800-123-4848"):
        assert stale not in text, stale
