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
_PROGRAMS = ["B.Tech CSE", "B.Tech ECE", "B.Tech ME", "MBA", "BBA", "B.Des"]
_EXAMS = ["JEE Main", "CUET", "CAT", "NMAT", None, None]   # None = not given
_STATUSES = ["new", "contacted", "qualified", "converted", "lost"]

# 30 lead templates: (name, email, phone, city, program, pct, exam, budget, scholarship, channel, score, tier, status)
_LEADS: list[tuple] = [
    # ── HOT (score ≥ 70) ──────────────────────────────────────────────────
    ("Aarav Sharma",    "aarav.sharma@gmail.com",    "9876543210", "Jaipur",    "B.Tech CSE", 92.0, "JEE Main", 8.0,  True,  "web",       88, "hot",  "qualified"),
    ("Diya Mehta",      "diya.mehta@gmail.com",      "9123456780", "Delhi",     "B.Tech CSE", 88.5, "JEE Main", 7.5,  True,  "whatsapp",  84, "hot",  "qualified"),
    ("Rohan Verma",     "rohan.verma@outlook.com",   "9988776655", "Mumbai",    "MBA",        85.0, "CAT",      10.0, False, "email",     80, "hot",  "contacted"),
    ("Priya Nair",      "priya.nair@yahoo.com",       "9871234560", "Pune",      "B.Tech ECE", 90.0, "JEE Main", 6.0,  True,  "web",       86, "hot",  "qualified"),
    ("Arjun Singh",     "arjun.singh@gmail.com",     "9765432109", "Ahmedabad", "B.Tech CSE", 91.0, "JEE Main", 9.0,  True,  "web",       90, "hot",  "converted"),
    ("Sneha Iyer",      "sneha.iyer@gmail.com",      "9654321098", "Jaipur",    "B.Des",      86.0, "CUET",     5.5,  False, "whatsapp",  75, "hot",  "qualified"),
    ("Vikram Patel",    "vikram.patel@gmail.com",    "9543210987", "Lucknow",   "B.Tech ME",  87.5, "JEE Main", 7.0,  True,  "email",     79, "hot",  "contacted"),
    ("Ananya Gupta",    "ananya.gupta@gmail.com",    "9432109876", "Delhi",     "BBA",        83.0, "CUET",     4.5,  True,  "web",       72, "hot",  "new"),
    ("Kartik Joshi",    "kartik.joshi@gmail.com",    "9321098765", "Hyderabad", "B.Tech CSE", 89.0, "JEE Main", 8.5,  False, "whatsapp",  82, "hot",  "qualified"),
    ("Meera Pillai",    "meera.pillai@gmail.com",    "9210987654", "Pune",      "MBA",        84.0, "CAT",      11.0, True,  "email",     85, "hot",  "converted"),
    # ── WARM (score 40–69) ────────────────────────────────────────────────
    ("Rahul Dubey",     "rahul.dubey@gmail.com",     "9109876543", "Bhopal",    "B.Tech ME",  72.0, "JEE Main", 4.0,  False, "web",       60, "warm", "contacted"),
    ("Pooja Yadav",     "pooja.yadav@gmail.com",     "9098765432", "Mumbai",    "BBA",        68.0, "CUET",     3.5,  False, "whatsapp",  55, "warm", "new"),
    ("Amit Kapoor",     "amit.kapoor@outlook.com",   "8987654321", "Jaipur",    "B.Tech CSE", 75.0, None,       5.0,  False, "email",     58, "warm", "new"),
    ("Kavya Reddy",     "kavya.reddy@gmail.com",     "8876543210", "Hyderabad", "B.Tech ECE", 71.0, "JEE Main", 4.5,  True,  "web",       65, "warm", "contacted"),
    ("Nikhil Bansal",   "nikhil.bansal@gmail.com",   "8765432109", "Delhi",     "MBA",        69.0, "CAT",      6.0,  False, "whatsapp",  62, "warm", "new"),
    ("Ritika Saxena",   "ritika.saxena@gmail.com",   "8654321098", "Lucknow",   "B.Des",      73.0, "CUET",     3.0,  False, "email",     50, "warm", "new"),
    ("Siddharth Tiwari","siddharth.t@gmail.com",     "8543210987", "Pune",      "B.Tech CSE", 76.0, "JEE Main", 5.5,  True,  "web",       68, "warm", "qualified"),
    ("Tanvi Mishra",    "tanvi.mishra@gmail.com",    "8432109876", "Ahmedabad", "BBA",        65.0, None,       2.5,  False, "whatsapp",  45, "warm", "lost"),
    ("Yash Agarwal",    "yash.agarwal@gmail.com",    "8321098765", "Bhopal",    "B.Tech ME",  70.0, "JEE Main", 4.0,  False, "web",       57, "warm", "contacted"),
    ("Pallavi Shukla",  "pallavi.shukla@gmail.com",  "8210987654", "Mumbai",    "MBA",        74.0, "CAT",      7.0,  True,  "email",     66, "warm", "new"),
    # ── COLD (score < 40) ─────────────────────────────────────────────────
    ("Deepak Kumar",    "deepak.kumar@gmail.com",    "8109876543", "Lucknow",   "B.Tech CSE", 52.0, None,       1.5,  False, "web",       30, "cold", "new"),
    ("Shweta Pandey",   "shweta.pandey@gmail.com",   "8098765432", "Delhi",     "BBA",        48.0, None,       2.0,  False, "whatsapp",  25, "cold", "lost"),
    ("Gaurav Chauhan",  "gaurav.chauhan@gmail.com",  "7987654321", "Jaipur",    "B.Tech ME",  55.0, "JEE Main", 1.0,  False, "email",     32, "cold", "new"),
    ("Nidhi Srivastava","nidhi.s@gmail.com",         "7876543210", "Bhopal",    "B.Des",      50.0, None,       1.5,  False, "web",       20, "cold", "lost"),
    ("Manish Tomar",    "manish.tomar@gmail.com",    "7765432109", "Ahmedabad", "MBA",        58.0, "CAT",      3.0,  False, "whatsapp",  38, "cold", "new"),
    ("Ankita Rawat",    "ankita.rawat@gmail.com",    "7654321098", "Hyderabad", "BBA",        45.0, None,       1.0,  False, "email",     22, "cold", "new"),
    ("Suresh Prajapat", "suresh.p@gmail.com",        "7543210987", "Pune",      "B.Tech CSE", 60.0, None,       2.0,  False, "web",       28, "cold", "contacted"),
    ("Reena Holkar",    "reena.holkar@gmail.com",    "7432109876", "Lucknow",   "B.Tech ECE", 53.0, None,       1.5,  False, "whatsapp",  18, "cold", "lost"),
    ("Tushar Bhatt",    "tushar.bhatt@gmail.com",    "7321098765", "Delhi",     "B.Des",      47.0, None,       1.0,  False, "email",     15, "cold", "new"),
    ("Geeta Solanki",   "geeta.solanki@gmail.com",   "7210987654", "Mumbai",    "BBA",        44.0, None,       0.8,  False, "web",       12, "cold", "new"),
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
_OUTBOUND_MSG = [
    "Thank you for your interest in JKLU! Here is our detailed brochure.",
    "Our counsellor will call you within 24 hours.",
    "Great score! You qualify for our merit scholarship.",
    "The next batch starts in July 2027. Seats are filling fast.",
    "We have EMI options available. Would you like details?",
    "Please fill in the online application form at admissions.jklu.edu.in.",
]


def _random_interaction(lead_id: int, channel: str) -> Interaction:
    direction = random.choice(["inbound", "outbound"])
    msg = random.choice(_INBOUND_MSG if direction == "inbound" else _OUTBOUND_MSG)
    actor = "agent" if direction == "outbound" else "system"
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
    ("second.student@example.com", "Second Student", "Student@5678", "Delhi", "MBA"),
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
            email="admin@jklu.edu.in",
            full_name="Admin User",
            role="admin",
            password_hash=hash_password("Admin@1234"),
            is_active=True,
        )
        counsellors = [
            User(email="dr.sharma@jklu.edu.in",  full_name="Dr. Anita Sharma",
                 role="counsellor", password_hash=hash_password("Counsel@1"), is_active=True),
            User(email="ms.verma@jklu.edu.in",   full_name="Ms. Rekha Verma",
                 role="counsellor", password_hash=hash_password("Counsel@2"), is_active=True),
            User(email="mr.mathur@jklu.edu.in",  full_name="Mr. Sunil Mathur",
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
            row = Lead(
                name=name,
                email=email,
                phone=phone,
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

