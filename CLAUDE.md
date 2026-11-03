# PS-04 Admission Enquiry & Lead Nurturing Agent (JKLU AI-Buildathon 1.0)

Solo project (Rohit) built with Claude Code. Deadline: GitHub repo submitted before 15 Nov 2026, 12:00 PM (the brochure cover says the event is 16 Nov; confirm with organisers). Target "done" = 10 Nov. 11-14 Nov = buffer. **Feature freeze = 8 Nov.**

Read `docs/SPEC.md` (behaviour, APIs, agent design) and `docs/BUILD_PLAN.md` (phases) before changing anything.

## What we are building
An agentic AI system that handles a prospective student's whole journey: answers admission enquiries from a verified knowledge base (with citations), qualifies and scores the lead, keeps a mock CRM, books counsellor slots (clash handling + alternatives), plans follow-ups that adapt to the lead's behaviour, gates sensitive actions behind counsellor approval, and logs everything to an audit trail.

## Judging rubric (100 points). Build for this.
1. Agentic capabilities (30): visible plan -> tool calls -> verification; retries, clarifying questions, alternatives.
2. Domain accuracy (25): correct answers, ZERO fabricated facts, grounded in the KB with citations.
3. Architecture (20): modular code, clean DB design, streaming, multi-user.
4. Safety/governance (15): approval gates, RBAC (admin/counsellor/student), audit log of reasoning, tool calls, outputs, approvals.
5. Demo/UX (10): smooth 5-minute end-to-end story with dashboards.
Simple LLM wrappers and static chatbots score poorly: the agent loop must really plan, call tools, verify and recover.

## Non-negotiable rules
- Never invent institutional facts (fees, dates, eligibility, policies). No KB answer -> say so and escalate.
- Synthetic data and mock integrations only (CRM, WhatsApp, email, calendar). No real PII or systems.
- State-changing sensitive actions (fee waiver, bulk messages, booking override) go through `request_approval` and run only after a counsellor approves.
- `audit_log` is append-only. Every write and every agent step/tool call is logged.
- RBAC enforced on the server, not just hidden in the UI.
- Never commit `.env` or secrets.

## Stack and layout
Backend FastAPI + SQLAlchemy 2 + Alembic on Postgres (docker-compose, pgvector image). Agent LLM: Gemini via the `google-genai` SDK (key in `.env`, model in `LLM_MODEL`). Frontend: React 18 + Vite + TypeScript + Tailwind (+ lucide-react).

```
backend/app/
  main.py              mounts routers /agent /crm /intel /scheduling
  contracts/           models.py (pydantic shapes), stubs.py (fake tools), tools.py (the ONLY place agent imports tools from; USE_REAL_* flags)
  agent/               agent loop, Gemini client, prompts, SSE chat endpoint
  crm/                 db/ (base, models, alembic migrations), service.py, seed.py, router.py (leads, interactions, auth, approvals, audit)
  intel/               data/*.md knowledge base, retrieval.py (TF-IDF + relevance threshold), scoring.py, service.py, test_set.py (benchmark)
  scheduling/          slots, booking, mock channels, follow-ups, virtual clock
backend/tests/
frontend/src/modules/{agent,crm,intel,channels}/
```
Tools the agent may call are defined by the signatures in `contracts/stubs.py`; real implementations live in each module's `service.py` with identical signatures. Contracts may now be changed (solo project), but keep stubs, models, real services and tests in sync in the same commit.

## Current state (3 Nov 2026), NOTHING HAS BEEN RUN YET
Inherited from a 4-person start: `intel/` (KB, TF-IDF retrieval with threshold 0.18, scoring, 40+ question benchmark, 3 UI components) and `crm/` (models: users, leads, interactions, approvals, audit_log; migration 0001; service layer; seed; lead + interaction endpoints) exist and match the contract signatures. `agent/` and `scheduling/` are placeholders. Frontend is a Vite shell with Intel and Channels pages.

Known issues to fix in Phase 0:
1. `.env.example` uses `postgresql://buildathon:buildathon@localhost:5432/admissions` but `crm/db/base.py` defaults to a different DB and uses the psycopg3 driver (`postgresql+psycopg://...`). Unify on `postgresql+psycopg://buildathon:buildathon@localhost:5432/admissions`.
2. `.env` is never loaded (`load_dotenv` missing in `main.py`).
3. Some CRM files cite a `RULES.md` that does not exist: create a short one or fix the references.
4. Requirements are incomplete: add PyJWT, alembic, python-multipart, google-genai.
5. Frontend nav labels contain teammates' names; rebuild navigation by role.
6. Verify that tests, migration, seed, server and `npm run build` actually work.

## Commands (run from repo root unless noted)
```
docker compose up -d db
cd backend && python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
alembic -c app/crm/db/alembic.ini upgrade head
python -m app.crm.seed
uvicorn app.main:app --reload          # http://localhost:8000/docs
pytest -q
cd ../frontend && npm install && npm run dev   # http://localhost:5173
```

## Conventions
- Python 3.11+, type hints, small functions, docstrings on public functions. Pydantic models for all API bodies.
- Commit after every working step, message prefix `agent:` `crm:` `intel:` `sched:` `web:` `docs:` `chore:`.
- Add or update a pytest for every behaviour in SPEC section "Scenarios".
- No new dependencies without a reason; list them in `requirements.txt` / `package.json`.

## How to work (instructions to Claude)
- Before coding a phase: read the relevant files, then give a short plan and wait for OK.
- Work in small verifiable steps; run the code and tests yourself and show the output. Do not claim something works unless you ran it.
- If a plan item is blocked or looks wrong, say so instead of working around it silently.
- Priority if time runs short (cut from the bottom): agent loop with grounding > booking with clash handling > approvals + RBAC + audit > adaptive follow-ups > dashboard polish > analytics tab > KB admin page > email inbox view.
