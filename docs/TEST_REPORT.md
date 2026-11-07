# Test report

Results from 7 Nov 2026. Every number below comes from a real run; re-run the commands to check them.

| Test | Result | What it shows |
|---|---|---|
| Automated tests (`pytest -q`) | **217 passed** | Behaviour of every module, with a scripted model and a throwaway database |
| Live model smoke test (`pytest -m live`) | **2 passed** | Fee answer and waiver request, on the real model |
| All scenarios on the real model (`scripts/live_scenarios.py`) | **19 of 20 checks passed** | The agent's real behaviour, including its wording |
| Retrieval benchmark (Knowledge page or `GET /intel/benchmark`) | **45 of 45 passed** | The right knowledge-base passage is found, and out-of-scope questions are refused |
| Full demo in the browser | **Completed in one take** | S1 to S7 and the audit log, through the UI |

The benchmark tests retrieval only, not the model's wording. There are no automated frontend tests: screens were checked by `npm run build` and by hand in a browser.

## Scenarios on the real model

Model `gemini-3.5-flash-lite`, fallback `gemini-3.6-flash`, with an 8-second pause between messages to match demo pace. A dash means the step made no chat request of its own.

| Scenario | Check | Result | Seconds |
|---|---|---|---|
| S1 | Cited answer with the fee from the KB | pass | 11.2 |
| S2 | Not in the KB: passed to a counsellor | pass | 8.2 |
| S2 | Unknown figure: says it doesn't have it, invents nothing | pass | 10.2 |
| S3 | First details saved, not scored yet | **fail** (see below) | 13.2 |
| S3 | Complete profile scored Hot, with reasons | pass | 12.8 |
| S4 | Clash refused with alternatives, no double booking | pass | 31.1 |
| S5 | The reply doesn't blame a taken slot | pass | 19.6 |
| S5 | Two retries, then alternatives, nothing booked | pass | 19.6 |
| S4 | Booked once the calendar recovered | pass | 9.5 |
| S6 | Hot silent lead gets a follow-up | pass | 3.6 |
| S6 | Opted-out lead refused | pass | – |
| S6 | Agent wrote the scholarship follow-up from the KB | pass | – |
| S7 | Waiver stays pending and says so, one request only | pass | 9.3 |
| S7 | Before a decision: reports it pending, no false claim | pass | 7.6 |
| S7 | Fee waiver approved by a counsellor, student notified | pass | – |
| S7 | Audit shows reasoning, tools and the approval | pass | – |
| S8 | Student and counsellor refused; the right roles allowed | pass | – |
| S9 | Opted out at once; later messages refused | pass | 0.1 |
| S10 | Direct injection refused without calling the model | pass | 0.1 |
| S10 | A claimed approval from a counsellor isn't repeated | pass | 8.9 |

**The failure:** the model scored a partial profile one message earlier than the check expected. Nothing wrong was shown or stored, and the spec doesn't require a particular moment, so the check was too strict. It now confirms the details were saved. The run hasn't been repeated since that change, because no agent code changed.

**Speed:** 12 model turns, median 11.2 seconds, slowest 31.1. The slow one came from a real timeout that the fallback model recovered from.

**Accuracy:** beyond these checks, I compared the fees, scholarship bands and placement figures in the replies with the KB text. They matched.

## Pytest coverage of the scenarios

Each scenario has tests with a scripted model in `tests/test_scenarios.py`: S1 (1), S2 (2), S3 (2), S4 (1), S5 (5), S6 (6), S7 (7), S8 (1), S9 (2), S10 (5). In all, there are 217 tests across these files:

| File | Tests | Covers |
|---|---|---|
| `test_governance.py` | 64 | Roles on every route, tokens, approvals, append-only audit |
| `test_scenarios.py` | 48 | S1 to S10 |
| `test_agent_verify.py` | 30 | Grounding, booking, false-grant and figure checks |
| `test_hardening.py` | 21 | Model fallback, rate limits, crash handling, demo seed |
| `test_scheduling.py` | 17 | Booking races, clock, follow-ups, opt-out |
| `test_agent_chat.py` | 15 | Agent loop, streaming, timeouts |
| `test_ui_api.py` | 15 | Endpoints the screens rely on |
| `test_intel.py` | 7 | Retrieval and scoring |

## Timed demo

One take through `docs/DEMO_SCRIPT.md` in a browser. These are waits for the agent, not including talking.

| Step | Wait (seconds) |
|---|---|
| S1 fee and eligibility | 11.0 |
| S2 hostel waiver | 7.3 |
| S3 first details | about 36 (a real timeout; the fallback recovered) |
| S3 complete profile | 12.0 |
| S4 clash | 5.8 |
| S5 calendar failure | 12.0 |
| S5 booking after recovery | 7.1 |
| S6 fast-forward 24h | 5.3 |
| S7 waiver request | 9.2 |
| **Total** | **about 105** |

That leaves over 3 minutes for talking, or about 2.5 minutes if several calls time out. This run used one browser and switched logins, and it armed the failure with a direct admin request so the student's clash card stayed on screen. The two-window setup in the script, and the speaking pace, still need a human rehearsal.

## What the live runs found

Pytest was all green while these bugs existed, because a scripted model says what the test expects. All are fixed, with tests, except where noted.

| Found | Effect |
|---|---|
| A waiver reply containing any figure was escalated as well | Two approvals, and the student got "I won't guess" instead of "pending" |
| "Has my waiver been approved?" with a date in the reply | Generic reply and a new escalation |
| Any earlier approval switched off the false-grant check for that lead | A waiver could have been wrongly claimed after an unrelated question was answered |
| Two sources in one citation bracket | Skipped by the grounding check and shown as raw text |
| Model sent `slot_40` instead of `40` | The booking was refused |
| Calendar failure described as "slot is taken" | Contradicted the card on screen |
| Failed-booking alternatives ignored the slot wanted, or included it | Offered the failed slot, or sessions days away |
| The scholarship follow-up searched with the wrong words | Fell back to a fixed template |
| Seeded agent lines stated invented facts, such as a batch date and EMI options | Would have been visible on every lead |
| Model said "you qualify for a 100% scholarship" | Now rejected as a false grant, and it describes the band instead |

## Known gaps

- **Wording varies.** The real model doesn't give identical replies each run. Code checks catch invented figures, unretrieved sources, false bookings and false grants, but not everything:
  - An uncited general remark in a qualification reply, such as "you're in a strong position for scholarships", isn't checked. Rule 1 in the prompt forbids it, and it appeared in one run.
  - "Your budget covers the fees" passed unchecked, because it states no figure.
- **Rate limits.** Running scenarios back to back hit a rate limit on both models. A demo at normal pace should stay under it, but the limits themselves are not measured, and a shared key or practice just beforehand could hit them.
- **Dependency warnings.** See Known limitations in the [README](../README.md).
