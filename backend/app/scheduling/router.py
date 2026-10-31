# Owner: Riya. Counsellor slots, booking, follow-up scheduler, mock WhatsApp/email.
# Real functions go in app/scheduling/service.py with the same signatures as contracts/stubs.py.
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {"module": "scheduling", "ok": True}
