# Owner: Dev. DB schema, mock CRM, auth/RBAC, approvals, audit log.
# Real functions go in app/crm/service.py with the same signatures as contracts/stubs.py.
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {"module": "crm", "ok": True}
