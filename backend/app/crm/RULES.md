# Project rules (CRM, security, audit)

Short version of the non-negotiables in the root `CLAUDE.md`; that file wins on any conflict.

- Never invent institutional facts. No KB answer -> say so and escalate.
- Synthetic data and mock integrations only. No real PII.
- Real service functions keep the exact signatures and return types of `contracts/stubs.py`.
- Every write calls `log_event`. `audit_log` is append-only: no update or delete helpers.
- Sensitive actions (fee waiver, scholarship promise, bulk messages, booking override,
  reversing an opt-out) go through `request_approval` and run only when `status == "approved"`.
- A lead's opt-out applies immediately and is always logged.
- RBAC is enforced on the server.
- Secrets come from the environment (`.env`, never committed). Never hardcode connection strings.
- On Windows, write files as UTF-8 without BOM.
