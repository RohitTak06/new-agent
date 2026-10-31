# Owner: Guru. Knowledge base, retrieval with citations, lead scoring.
# Real functions go in app/intel/service.py with the same signatures as contracts/stubs.py.
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {"module": "intel", "ok": True}
