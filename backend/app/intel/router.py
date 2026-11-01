# Owner: Guru. Knowledge base, retrieval with citations, lead scoring.
from fastapi import APIRouter
from pydantic import BaseModel

from app.contracts.models import KnowledgeResult, LeadProfile, LeadScore
from app.intel.retrieval import search_knowledge, store
from app.intel.scoring import score_lead
from app.intel.test_set import run_benchmark_evaluation

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    top_k: int = 3


@router.get("/health")
def health():
    return {"module": "intel", "ok": True, "indexed_chunks": len(store.raw_chunks)}


@router.post("/search", response_model=KnowledgeResult)
def search_endpoint(req: SearchRequest):
    """Retrieve institutional knowledge chunks for a query with citation tags."""
    return search_knowledge(req.query)


@router.post("/score", response_model=LeadScore)
def score_endpoint(profile: LeadProfile):
    """Qualify and score a prospective student lead profile."""
    return score_lead(profile)


@router.get("/knowledge")
def list_knowledge_chunks():
    """Returns all indexed knowledge chunks for KB admin review."""
    return {
        "count": len(store.raw_chunks),
        "chunks": [
            {"source": src, "preview": txt[:140] + ("..." if len(txt) > 140 else "")}
            for txt, src in store.raw_chunks
        ]
    }


@router.post("/knowledge/reload")
def reload_knowledge():
    """Reloads knowledge store from markdown files."""
    store.reload()
    return {"status": "reloaded", "total_chunks": len(store.raw_chunks)}


@router.get("/benchmark")
def run_benchmark():
    """Runs the 40+ question benchmark test suite and returns precision and guardrail metrics."""
    return run_benchmark_evaluation()
