# BUILD PLAN (solo with Claude Code), 3 Nov to 10 Nov 2026

How to use: start Claude Code in the repo root (`claude`), it will read `CLAUDE.md`. For each phase paste the prompt block. Claude will show a plan first: read it, then say "go". At the end of each phase run the acceptance check yourself, commit and push.

| Phase | When | Goal |
|---|---|---|
| 0 | Mon 3 Nov (tonight) | Bootstrap, fix known issues, everything runs |
| 1 | Tue 4 Nov | Agent core: Gemini + loop + SSE + trace + minimal chat page |
| 2 | Tue-Wed 4-5 Nov | Scheduling backend: slots, booking, mock channels, follow-ups, virtual clock |
| 3 | Wed 5 Nov | Auth/RBAC, approvals, audit endpoints |
| 4 | Thu 6 Nov | Full agent behaviours + scenario tests S1-S10 |
| 5 | Fri-Sat 7-8 Nov | Frontend: all screens. **Freeze Sat 8 Nov night** |
| 6 | Sun-Mon 9-10 Nov | Hardening, demo data, README, diagram, deck, backup video |
| buffer | 11-14 Nov | Bug fixes only, final push |

If behind: cut in the order given in CLAUDE.md ("Priority if time runs short").

---
## Phase 0: Bootstrap and verify
Prereqs: Docker Desktop, Python 3.11+, Node 18+, a Gemini API key from Google AI Studio.
```
Read CLAUDE.md and docs/SPEC.md. Phase 0 goal: make the inherited code actually run.
1. Fix the known issues listed in CLAUDE.md (DATABASE_URL + driver, load_dotenv, RULES.md references, requirements incl. PyJWT, alembic, python-multipart, google-genai).
2. Bring up Postgres with docker compose, run the alembic migration and the seed script, start uvicorn, hit /health and /docs for every router.
3. Run pytest and the /intel/benchmark endpoint; report the pass rate and list failing questions.
4. Run `npm install` and `npm run build` in frontend; fix errors.
5. Set USE_REAL_INTEL=1 and USE_REAL_CRM=1 in .env.example defaults and prove through a small script that contracts/tools.py calls the real services.
Show me what you ran and the output at each step. Do not start building new features.
```
Acceptance: uvicorn up, migrations + seed OK, pytest green, benchmark number known, frontend builds.

## Phase 1: Agent core
```
Phase 1: build the agent core in backend/app/agent/ per docs/SPEC.md section 2.
- llm.py: thin Gemini client using the google-genai SDK (read LLM_API_KEY, LLM_MODEL from env). Fetch the current official docs for function calling and streaming first; do not guess the API.
- tools_schema.py: function declarations for every tool in SPEC 2.3 (start with search_knowledge, score_lead, upsert_lead, get_lead; scheduling tools stay on stubs for now).
- loop.py: PLAN -> ACT -> VERIFY -> RETRY/REPLAN -> RESPOND with the deterministic verifiers (grounding check, no fake bookings), max 8 steps, bounded retries.
- router.py: POST /agent/chat streaming SSE with the event schema in SPEC 2.2. Persist each event to audit_log via crm.service.log_event, and messages as interactions.
- A minimal React chat page in frontend/src/modules/agent/ that shows the streamed answer and a side panel listing plan/tool_call/tool_result/verify events live.
Write pytest tests with the LLM mocked for scenarios S1 and S2 first. Show me the plan before coding.
```
Acceptance: ask "B.Tech CSE fees?" in the UI -> cited answer + visible trace; ask about hostel fee waiver -> refusal + escalation event.

## Phase 2: Scheduling backend
```
Phase 2: implement backend/app/scheduling/ per SPEC sections 2.5, 3, 4.
- Alembic migration 0002: counsellors, slots, messages, followups, sessions.
- clock.py virtual clock with advance endpoint.
- service.py with real get_slots, book_slot (atomic, clash detection, alternatives = nearest free slots), send_message (stores to messages, channel whatsapp|email, no real sending), schedule_followup. Same signatures and return types as contracts/stubs.py.
- scheduler: APScheduler job that sends due follow-ups using the virtual clock, honouring opt-out, logging to audit.
- Seed counsellors and slots for the next 7 virtual days.
- Endpoints per SPEC section 4 (/scheduling).
- pytest: double booking prevented under two concurrent requests, alternatives returned, due follow-up fires after clock advance.
Show the plan first, then implement. Flip USE_REAL_SCHEDULING=1 when tests pass.
```
Acceptance: S4 and S6 logic passes at service level.

## Phase 3: Auth, RBAC, approvals, audit
```
Phase 3: finish the CRM governance layer per SPEC sections 4 and 5.
- POST /crm/auth/login (JWT), GET /crm/auth/me, require_role dependency, apply to every non-public endpoint across all routers. Seed users: admin, two counsellors, two students.
- Approvals: list/approve/reject endpoints and the executor registry (fee_waiver, booking_override, bulk_message, escalate_question). Every state change writes audit_log.
- GET /crm/audit with filters, and GET /crm/analytics/funnel.
- Students may only read their own lead, messages and sessions.
- pytest for S7 (service level), S8 and S9.
Show the plan first.
```
Acceptance: S8 passes; approving a fee waiver executes it and logs it.

## Phase 4: Full agent behaviours
```
Phase 4: complete the agent behaviours using the real scheduling and CRM modules.
- Qualification flow (SPEC 2.4) with clarifying questions.
- Booking flow with alternatives on clash and the failure fallback when the calendar tool errors (inject failures in a test).
- Sensitive-action wrappers that go through request_approval; student gets "pending counsellor approval". Handle approval outcomes (notify student).
- Adaptive follow-up planner (SPEC 2.5): policy in code, wording by LLM with KB citations for scholarship/objection messages.
- Prompt-injection defence (S10): system prompt rules + code-level checks so nothing sensitive runs without approval.
- Make scenarios S1-S10 pytest tests (LLM mocked where needed) and one optional live-LLM smoke test marked @pytest.mark.live.
Report which scenarios pass. Show the plan first.
```
Acceptance: all S1-S10 green.

## Phase 5: Frontend (freeze Sat 8 Nov)
```
Phase 5: build the frontend per CLAUDE.md layout. Replace the name-labelled navigation with role-based navigation and a login page.
Student side: web chat with live trace panel; fake WhatsApp phone view and email inbox view showing messages from /scheduling/messages; booking confirmation card with alternatives.
Staff side: lead pipeline (kanban by hot/warm/cold), lead detail (profile, score reasons, interactions, messages, bookings), approval inbox (approve/reject), audit log viewer with filters, scheduling view with a "fast-forward time" button, knowledge admin (existing), simple funnel analytics.
Use the existing Intel components (LeadScoreCard, CitationDisplay, KnowledgeAdmin). Handle loading and error states. Keep it clean and consistent with Tailwind. Build one screen at a time and show me each before the next.
```
Acceptance: the 5-minute demo can be driven entirely from the UI.

## Phase 6: Hardening and delivery
```
Phase 6: hardening and delivery.
1. Add a one-command demo seed (leads, counsellors, slots, KB loaded) and a `make demo` or script to start everything.
2. Run all scenarios and the intel benchmark; write docs/TEST_REPORT.md with the numbers.
3. Write README.md: overview, architecture diagram (mermaid), setup, rubric mapping, safety design, limitations.
4. Review error handling, logging, DB indexes, and secrets. Check a fresh clone runs from the README alone.
5. Write docs/DEMO_SCRIPT.md (5 minutes, SPEC section 7) with exact messages to type.
```
Then: dress rehearsal twice, record a backup video, push, tag `v1.0`.
