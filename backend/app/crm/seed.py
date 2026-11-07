"""CRM seed — synthetic data only. No real student data.

Run once (idempotent: bails if users already exist):
    python -m app.crm.seed

Creates:
    1  admin
    3  counsellors
    2  students, each linked to their own lead
   30  leads  (mixed tiers, channels, cities)
    2-4 interactions per lead

Passwords are hashed with pbkdf2:sha256 (stdlib, no extra packages).
Scores and tiers are hardcoded — no intel service imported.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.crm.db.base import SessionLocal
from app.crm.db.models import Interaction, Lead, User
from app.crm.service import hash_password

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
random.seed(42)

# ---------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------

_CITIES = ["Jaipur", "Delhi", "Mumbai", "Pune", "Ahmedabad", "Lucknow", "Hyderabad", "Bhopal"]
_CHANNELS = ["web", "whatsapp", "email"]
_PROGRAMS = ["B.Tech CSE", "B.Tech ECE (VLSI Design)", "B.Tech CSE (Data Science)", "BBA", "BBA", "B.Des"]
_EXAMS = ["JEE Main", "CUET", "CUET", "CUET", None, None]   # None = not given
_STATUSES = ["new", "contacted", "qualified", "converted", "lost"]

# 30 lead templates: (name, email, phone, city, program, pct, exam, budget, scholarship, channel, score, tier, status)
_LEADS: list[tuple] = [
    # ── HOT (score ≥ 70) ──────────────────────────────────────────────────
    ("Aarav Sharma",    "aarav.sharma@example.test",    "9000000001", "Jaipur",    "B.Tech CSE", 92.0, "JEE Main", 8.0,  True,  "web",       88, "hot",  "qualified"),
    ("Diya Mehta",      "diya.mehta@example.test",      "9000000002", "Delhi",     "B.Tech CSE", 88.5, "JEE Main", 7.5,  True,  "whatsapp",  84, "hot",  "qualified"),
    ("Rohan Verma",     "rohan.verma@example.test",   "9000000003", "Mumbai",    "BBA",        85.0, "CUET",      10.0, False, "email",     80, "hot",  "contacted"),
    ("Priya Nair",      "priya.nair@example.test",       "9000000004", "Pune",      "B.Tech ECE (VLSI Design)", 90.0, "JEE Main", 6.0,  True,  "web",       86, "hot",  "qualified"),
    ("Arjun Singh",     "arjun.singh@example.test",     "9000000005", "Ahmedabad", "B.Tech CSE", 91.0, "JEE Main", 9.0,  True,  "web",       90, "hot",  "converted"),
    ("Sneha Iyer",      "sneha.iyer@example.test",      "9000000006", "Jaipur",    "B.Des",      86.0, "CUET",     5.5,  False, "whatsapp",  75, "hot",  "qualified"),
    ("Vikram Patel",    "vikram.patel@example.test",    "9000000007", "Lucknow",   "B.Tech CSE (Data Science)",  87.5, "JEE Main", 7.0,  True,  "email",     79, "hot",  "contacted"),
    ("Ananya Gupta",    "ananya.gupta@example.test",    "9000000008", "Delhi",     "BBA",        83.0, "CUET",     4.5,  True,  "web",       72, "hot",  "new"),
    ("Kartik Joshi",    "kartik.joshi@example.test",    "9000000009", "Hyderabad", "B.Tech CSE", 89.0, "JEE Main", 8.5,  False, "whatsapp",  82, "hot",  "qualified"),
    ("Meera Pillai",    "meera.pillai@example.test",    "9000000010", "Pune",      "BBA",        84.0, "CUET",      11.0, True,  "email",     85, "hot",  "converted"),
    # ── WARM (score 40–69) ────────────────────────────────────────────────
    ("Rahul Dubey",     "rahul.dubey@example.test",     "9000000011", "Bhopal",    "B.Tech CSE (Data Science)",  72.0, "JEE Main", 4.0,  False, "web",       60, "warm", "contacted"),
    ("Pooja Yadav",     "pooja.yadav@example.test",     "9000000012", "Mumbai",    "BBA",        68.0, "CUET",     3.5,  False, "whatsapp",  55, "warm", "new"),
    ("Amit Kapoor",     "amit.kapoor@example.test",   "9000000013", "Jaipur",    "B.Tech CSE", 75.0, None,       5.0,  False, "email",     58, "warm", "new"),
    ("Kavya Reddy",     "kavya.reddy@example.test",     "9000000014", "Hyderabad", "B.Tech ECE (VLSI Design)", 71.0, "JEE Main", 4.5,  True,  "web",       65, "warm", "contacted"),
    ("Nikhil Bansal",   "nikhil.bansal@example.test",   "9000000015", "Delhi",     "BBA",        69.0, "CUET",      6.0,  False, "whatsapp",  62, "warm", "new"),
    ("Ritika Saxena",   "ritika.saxena@example.test",   "9000000016", "Lucknow",   "B.Des",      73.0, "CUET",     3.0,  False, "email",     50, "warm", "new"),
    ("Siddharth Tiwari","siddharth.t@example.test",     "9000000017", "Pune",      "B.Tech CSE", 76.0, "JEE Main", 5.5,  True,  "web",       68, "warm", "qualified"),
    ("Tanvi Mishra",    "tanvi.mishra@example.test",    "9000000018", "Ahmedabad", "BBA",        65.0, None,       2.5,  False, "whatsapp",  45, "warm", "lost"),
    ("Yash Agarwal",    "yash.agarwal@example.test",    "9000000019", "Bhopal",    "B.Tech CSE (Data Science)",  70.0, "JEE Main", 4.0,  False, "web",       57, "warm", "contacted"),
    ("Pallavi Shukla",  "pallavi.shukla@example.test",  "9000000020", "Mumbai",    "BBA",        74.0, "CUET",      7.0,  True,  "email",     66, "warm", "new"),
    # ── COLD (score < 40) ─────────────────────────────────────────────────
    ("Deepak Kumar",    "deepak.kumar@example.test",    "9000000021", "Lucknow",   "B.Tech CSE", 52.0, None,       1.5,  False, "web",       30, "cold", "new"),
    ("Shweta Pandey",   "shweta.pandey@example.test",   "9000000022", "Delhi",     "BBA",        48.0, None,       2.0,  False, "whatsapp",  25, "cold", "lost"),
    ("Gaurav Chauhan",  "gaurav.chauhan@example.test",  "9000000023", "Jaipur",    "B.Tech CSE (Data Science)",  55.0, "JEE Main", 1.0,  False, "email",     32, "cold", "new"),
    ("Nidhi Srivastava","nidhi.s@example.test",         "9000000024", "Bhopal",    "B.Des",      50.0, None,       1.5,  False, "web",       20, "cold", "lost"),
    ("Manish Tomar",    "manish.tomar@example.test",    "9000000025", "Ahmedabad", "BBA",        58.0, "CUET",      3.0,  False, "whatsapp",  38, "cold", "new"),
    ("Ankita Rawat",    "ankita.rawat@example.test",    "9000000026", "Hyderabad", "BBA",        45.0, None,       1.0,  False, "email",     22, "cold", "new"),
    ("Suresh Prajapat", "suresh.p@example.test",        "9000000027", "Pune",      "B.Tech CSE", 60.0, None,       2.0,  False, "web",       28, "cold", "contacted"),
    ("Reena Holkar",    "reena.holkar@example.test",    "9000000028", "Lucknow",   "B.Tech ECE (VLSI Design)", 53.0, None,       1.5,  False, "whatsapp",  18, "cold", "lost"),
    ("Tushar Bhatt",    "tushar.bhatt@example.test",    "9000000029", "Delhi",     "B.Des",      47.0, None,       1.0,  False, "email",     15, "cold", "new"),
    ("Geeta Solanki",   "geeta.solanki@example.test",   "9000000030", "Mumbai",    "BBA",        44.0, None,       0.8,  False, "web",       12, "cold", "new"),
]

# A pool of realistic interaction messages keyed by direction
_INBOUND_MSG = [
    "Hi, I saw your ad. Can you tell me more about admissions?",
    "What is the fee structure for B.Tech?",
    "Is there a scholarship for JEE qualified students?",
    "I scored 88% in Class 12. Am I eligible?",
    "When does the next batch start?",
    "Can I get a brochure?",
]
_OUTBOUND_MSG = [   # no institutional facts: seed data must never put words in the agent's mouth
    "Thanks for your message. I can answer from our verified information or pass you to a counsellor.",
    "A counsellor can call you to go through this. Would that help?",
    "I don't have that confirmed, so I've asked a counsellor to reply.",
    "Could you share your Class 12 percentage and entrance exam?",
    "Would you like to book a session with a counsellor?",
]


def _random_interaction(lead_id: int, channel: str) -> Interaction:
    direction = random.choice(["inbound", "outbound"])
    msg = random.choice(_INBOUND_MSG if direction == "inbound" else _OUTBOUND_MSG)
    actor = "agent" if direction == "outbound" else "student"
    return Interaction(
        lead_id=lead_id,
        actor=actor,
        channel=channel,
        direction=direction,
        message=msg,
        meta=None,
    )


# ---------------------------------------------------------------------------
# Seed entry-point
# ---------------------------------------------------------------------------

_STUDENTS = [
    ("test.student@example.com", "Test Student", "Student@1234", "Jaipur", "B.Tech CSE"),
    ("second.student@example.com", "Second Student", "Student@5678", "Delhi", "BBA"),
]


def ensure_students(db) -> int:
    """Create the two demo students and link each to their own lead. Safe to re-run."""
    linked = 0
    for email, name, password, city, program in _STUDENTS:
        user = db.scalars(select(User).where(User.email == email)).first()
        if user is None:
            user = User(email=email, full_name=name, role="student",
                        password_hash=hash_password(password), is_active=True)
            db.add(user)
            db.flush()
        lead = db.scalars(select(Lead).where(Lead.user_id == user.id)).first()
        if lead is None:
            db.add(Lead(user_id=user.id, name=name, email=email, city=city, program_interest=program,
                        channel="web", status="new"))
            linked += 1
    db.commit()
    return linked


def run_seed() -> None:
    db = SessionLocal()
    try:
        # Idempotency guard
        user_count = db.scalar(select(func.count(User.id)))
        if user_count and user_count > 0:
            print(f"[seed] Data already present; linked {ensure_students(db)} student lead(s).")
            return

        # ── Users ────────────────────────────────────────────────────────
        admin = User(
            email="admin@jklu.example",
            full_name="Admin User",
            role="admin",
            password_hash=hash_password("Admin@1234"),
            is_active=True,
        )
        counsellors = [
            User(email="dr.sharma@jklu.example",  full_name="Dr. Anita Sharma",
                 role="counsellor", password_hash=hash_password("Counsel@1"), is_active=True),
            User(email="ms.verma@jklu.example",   full_name="Ms. Rekha Verma",
                 role="counsellor", password_hash=hash_password("Counsel@2"), is_active=True),
            User(email="mr.mathur@jklu.example",  full_name="Mr. Sunil Mathur",
                 role="counsellor", password_hash=hash_password("Counsel@3"), is_active=True),
        ]

        db.add(admin)
        db.add_all(counsellors)
        db.flush()  # get IDs before leads

        counsellor_ids = [c.id for c in counsellors]

        # ── Leads ────────────────────────────────────────────────────────
        lead_rows: list[Lead] = []
        for (
            name, email, phone, city, program,
            pct, exam, budget, scholarship,
            channel, score, tier, status,
        ) in _LEADS:
            assigned = random.choice(counsellor_ids) if status not in ("new", "lost") else None
            # Weak leads rarely leave full contact details, and reachability carries a lot of score.
            row = Lead(
                name=name,
                email=None if tier == "cold" and channel == "whatsapp" else email,
                phone=None if tier == "cold" and channel != "whatsapp" else phone,
                city=city,
                program_interest=program,
                twelfth_percent=pct,
                entrance_exam=exam,
                budget_lakh=budget,
                asked_scholarship=scholarship,
                channel=channel,
                score=score,
                score_tier=tier,
                status=status,
                opted_out=False,
                assigned_to=assigned,
            )
            lead_rows.append(row)

        db.add_all(lead_rows)
        db.flush()  # get lead IDs

        # ── Interactions (2–4 per lead) ───────────────────────────────────
        interactions: list[Interaction] = []
        for row in lead_rows:
            count = random.randint(2, 4)
            for _ in range(count):
                interactions.append(_random_interaction(row.id, row.channel))

        db.add_all(interactions)
        db.commit()
        ensure_students(db)

        print(f"[seed] Created 1 admin, 3 counsellors, {len(_STUDENTS)} students, "
              f"{len(lead_rows)} leads, {len(interactions)} interactions.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()

