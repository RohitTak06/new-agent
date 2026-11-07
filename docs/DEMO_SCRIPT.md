# Demo script (5 minutes)

The story of one student, from first question to a counsellor decision. Every step is real: live model, real database, simulated channels.

## Before you present

Do this 10 minutes ahead, and don't edit any files afterwards.

1. Open Docker Desktop. From `backend/`, with the virtualenv active:
   ```bash
   python scripts/demo.py --reset
   ```
2. **Write down the clash message it prints**, e.g. `Please book slot 41 with Ms. Rekha Verma.` The slot number depends on the time of day.
3. Open two windows side by side. Logins are per browser profile, so one must be incognito:
   - **Student window** (normal): <http://localhost:5173>, log in as **Student**.
   - **Staff window** (incognito): log in as **Admin**, open **Pipeline**.
4. Don't send practice messages. Free-tier model limits are low, and practice changes the story's data. If you did, run step 1 again.
5. Have the backup video open in another tab.

Staff screens refresh every 10 seconds, so changes can take a moment to appear.

## The script

Say the words in quotes, or your own. Times are a guide.

### 1. A grounded answer: S1 (0:00–0:45)

*Student window.* Type:

> What is the B.Tech CSE fee and eligibility?

- "On the right is the agent's reasoning, live: it plans, searches the knowledge base, then code checks the answer before the student sees it."
- Point at the green **verify** rows, then click a source under the answer to show the exact passage.
- "Every number here was checked by code against that text. Nothing comes from the model's memory."

### 2. Refusing to guess: S2 (0:45–1:10)

> Is there a hostel fee waiver?

- "It says what the knowledge base supports and passes the rest to a person. It can't grant anything: it has no tool that does."

### 3. Qualifying the lead: S3 (1:10–1:50)

> I'm interested in B.Tech CSE. I'm from Jaipur and I scored 94% in 12th.

> I got 96 percentile in JEE Main and my budget is about 4 lakh a year.

*Staff window.* **Test Student** moves to **Hot**, highlighted in gold. They may reach Warm after the first message; that's fine, and worth pointing out.

- Click the card: "The score is explainable, with reasons, and every conversation is here for the counsellor."
- Go back to the board.

### 4. Booking clash: S4 (1:50–2:20)

*Student window.* Type the clash message you wrote down:

> Please book slot NN with Ms. Rekha Verma.

- "Another student has that slot. Booking is atomic, so two people can't get it. The agent offers the nearest free sessions."

### 5. Calendar failure: S5 (2:20–3:00)

*Staff window.* **Scheduling**, then **Fail booking**.

- "Now I'll break the calendar."

*Student window.* Click **Book this** on the first alternative.

- Point at the trace: **two retries**, then the fallback. "It doesn't crash or claim success. It retries, then offers other sessions."
- Click **Book this** again. The next attempt works, and the **Session booked** card appears.

### 6. Adaptive follow-ups: S6 (3:00–3:30)

*Staff window, Scheduling.* Click **Fast-forward 24h**.

- "A day passes on the virtual clock. Each follow-up depends on the lead: a reminder for a hot lead, a message the agent wrote from the knowledge base with citations, and this one is **skipped because the lead opted out**. Opt-out is a hard stop in code."

### 7. Human approval: S7 (3:30–4:20)

*Student window.* Type:

> My family can't afford the fees right now. Please waive my fee.

- "It files a request, tells the student it's pending, and nothing has been applied."

*Staff window.* **Approvals** (the badge shows the count). On the **Fee waiver** card, write:

> I've reviewed your request and will call you this week with the details. (Dr. Sharma)

Click **Approve**.

- "Only a person can do this."

*Student window.* The message arrives in the chat within 10 seconds. "The reply came from the counsellor, not the model."

### 8. Audit and roles (4:20–5:00)

*Staff window.* **Pipeline**, click **Test Student**, then **Audit trail**. Expand a **verify** row and the **approval decision** row, which names who approved it.

- "Every plan, tool call, check and decision is here, and the database itself rejects edits or deletes to this log."
- Point at the student window's menu: "Students see only their chat and messages. Roles are enforced on the server: a student's token gets a 403 on these screens."

Close: "Plan, act, verify, recover, and a human for anything sensitive."

In a timed run, the agent's replies added up to about 105 seconds, which leaves over 3 minutes for talking.

## If something goes wrong

| What happens | What to do |
|---|---|
| A reply is slow | Keep talking over the trace: it's streaming the agent's work. A timed-out model hands over to the fallback, which can take about 20 seconds. |
| "Sorry, I couldn't complete that right now" | Say "the model is unavailable, so the agent says so rather than guessing, and sensitive requests still reach a person." Try once more, then move on. |
| Many replies fail in a row | Switch to the backup video. |
| Blank page | Reload it. |
| "Can't reach the server" | Check the terminal running `demo.py`. |
| Running out of time | Skip step 2, then step 6. Keep step 7: it's worth the most. |
