"""Service layer for Knowledge and Lead Intelligence.
Implements the contract signatures for search_knowledge and score_lead.
"""
from app.contracts.models import KnowledgeResult, LeadProfile, LeadScore
from app.intel.retrieval import search_knowledge as _search
from app.intel.scoring import score_lead as _score


def search_knowledge(query: str) -> KnowledgeResult:
    """Institutional knowledge search with strict citation tracking and zero-hallucination guard."""
    return _search(query)


def score_lead(profile: LeadProfile) -> LeadScore:
    """Lead qualification and scoring engine."""
    return _score(profile)
