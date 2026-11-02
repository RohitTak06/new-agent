You are working on the CRM, Security and Audit module of a hackathon project
(JKLU AI-Buildathon, PS-04 admission agent). Owner: Dev.

Rules:
- Edit only backend/app/crm/ and frontend/src/modules/crm/.
- Never change backend/app/contracts/ without asking me first.
- Real functions must keep the exact signatures and return types of the stubs.
- Every write must call log_event.
- Anything that changes state goes through the approval gate. Never skip the
  status == "approved" check.
- Synthetic data only. No real student data. Never commit .env.
- On Windows, write all files as UTF-8 without BOM.
- Commit messages start with "crm:".