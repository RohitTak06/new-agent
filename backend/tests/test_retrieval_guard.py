"""Retrieval must not invent a match from keyword boosts, and must not refuse what the knowledge base covers.

No database: `pytest --noconftest tests/test_retrieval_guard.py`.
"""
import pytest

from app.intel.retrieval import store
from app.intel.test_set import run_benchmark_evaluation


@pytest.mark.parametrize("query", [
    "Can I get a message when results come out?",     # "mess" inside "message" used to match the hostel section
    "Do classrooms have smart boards?",               # "room" inside "classroom"
    "Do you have a math olympiad quota?",             # a boost alone, with no shared words
    "Is there a coffee shop?",
])
def test_a_boost_alone_is_not_a_match(query):
    assert store.search(query).answer_found is False


@pytest.mark.parametrize("query, source", [
    ("Is there a medical centre on campus?", "campus_and_facilities.md#health-and-wellness"),
    ("Is there a stipend for M.Tech GATE students?", "scholarships.md#master-of-technology-m-tech-scholarships"),
])
def test_questions_the_kb_answers_are_not_blocked_as_out_of_scope(query, source):
    result = store.search(query)
    assert result.answer_found and result.chunks[0].source == source


@pytest.mark.parametrize("query", [
    "Can I get an admission in MBBS or medical college at JKLU?",
    "What is the monthly stipend given to all B.Tech students?",
])
def test_out_of_scope_traps_still_refused(query):
    assert store.search(query).answer_found is False


def test_benchmark_still_passes_in_full():
    result = run_benchmark_evaluation()
    assert result["passed"] == result["total_questions"], result.get("failures")
