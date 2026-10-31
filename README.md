# JKLU AI-Buildathon 1.0: PS-04 Admission Enquiry and Lead Nurturing Agent

Team: Rohit, Dev, Guru, Riya

## Modules and owners

| Module | Owner | Backend folder | Frontend folder |
|---|---|---|---|
| Agent Brain | Rohit | `backend/app/agent/` | `frontend/src/modules/agent/` |
| CRM, Security and Audit | Dev | `backend/app/crm/` | `frontend/src/modules/crm/` |
| Knowledge and Lead Intelligence | Guru | `backend/app/intel/` | `frontend/src/modules/intel/` |
| Scheduling and Channels | Riya | `backend/app/scheduling/` | `frontend/src/modules/channels/` |

Shared contracts (function signatures, data models, stubs): `backend/app/contracts/`. Change them only through a PR that all 4 approve.

## Run it

```bash
cp .env.example .env
docker compose up -d db          # Postgres + pgvector
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload    # http://localhost:8000/docs
```

## Stub to real switch

Every tool the agent calls goes through `app/contracts/tools.py`. By default it returns hardcoded stub data. When your real module is ready, set its flag in `.env`:

```
USE_REAL_INTEL=1        # Guru: search_knowledge, score_lead
USE_REAL_CRM=1          # Dev: upsert_lead, get_lead, request_approval
USE_REAL_SCHEDULING=1   # Riya: get_slots, book_slot, send_message, schedule_followup
```

The agent code never changes.

## Docs
- `docs/GIT_WORKFLOW.md`: branching and PR rules
- Each owner adds their module section to this README by Day 9.
