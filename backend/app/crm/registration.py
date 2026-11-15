"""Student self-registration: one account and one lead per student, with consent recorded.

Only a student registers here; staff accounts come from the seed. Consent to be contacted is
set only by this path (it is not part of LeadProfile, so the agent can never set it). If the
email already belongs to a lead from a chat without an account, that lead is linked instead of
creating a duplicate.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.crm.db.base import SessionLocal
from app.crm.db.models import Lead as LeadRow
from app.crm.db.models import User
from app.crm.service import hash_password, log_event

# Programmes as named in backend/app/intel/data/programs_and_fees.md (a test keeps them in step).
COURSES = [
    "B.Tech CSE (Computer Science and Engineering)",
    "B.Tech CSE AI (Artificial Intelligence)",
    "B.Tech CSE (Cybersecurity)",
    "B.Tech CSE (Data Science)",
    "B.Tech ECE (VLSI Design)",
    "Master of Technology (M.Tech)",
    "Bachelor of Business Administration (BBA)",
    "BBA (Fintech)",
    "BBA (Honours)",
    "BBA Honours in Supply Chain and Logistics",
    "Bachelor of Design (B.Des)",
    "Master of Design (M.Des)",
    "Doctor of Philosophy (PhD)",
]

# The 28 states and 8 union territories of India.
STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
    "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu", "Delhi",
    "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]

COUNTRY_CODES = ["+91"]
MIN_PASSWORD = 8
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^\d{10}$")


class RegisterIn(BaseModel):
    """What the register form sends. Every rule here is checked again on the server, whatever the form did."""

    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    email: str = Field(max_length=255)
    country_code: str = "+91"
    phone: str
    state: str
    city: str = Field(min_length=1, max_length=100)
    course: str
    lateral_entry: bool = False
    password: str = Field(min_length=MIN_PASSWORD, max_length=128)
    consent: bool

    @field_validator("first_name", "last_name", "city", mode="before")
    @classmethod
    def _trimmed(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, value):
        value = value.strip().lower() if isinstance(value, str) else value
        if not isinstance(value, str) or not _EMAIL.match(value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("country_code")
    @classmethod
    def _country_code(cls, value: str) -> str:
        if value not in COUNTRY_CODES:
            raise ValueError(f"Country code must be one of {', '.join(COUNTRY_CODES)}")
        return value

    @field_validator("phone", mode="before")
    @classmethod
    def _phone(cls, value):
        value = re.sub(r"[\s-]", "", value) if isinstance(value, str) else value
        if not isinstance(value, str) or not _PHONE.match(value):
            raise ValueError("Mobile number must be 10 digits")
        return value

    @field_validator("state")
    @classmethod
    def _state(cls, value: str) -> str:
        if value not in STATES:
            raise ValueError("Choose a state or union territory from the list")
        return value

    @field_validator("course")
    @classmethod
    def _course(cls, value: str) -> str:
        if value not in COURSES:
            raise ValueError("Choose a course from the list")
        return value

    @field_validator("consent")
    @classmethod
    def _consent(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Consent to be contacted is required to register")
        return value


class EmailTaken(Exception):
    """An account already uses this email."""


def options() -> dict:
    """The lists the register form shows, from the same source the server validates against."""
    return {"country_codes": COUNTRY_CODES, "states": STATES, "courses": COURSES, "min_password": MIN_PASSWORD}


def _public_input(data: RegisterIn) -> dict:
    """What the audit log keeps of a registration: everything but the password."""
    return data.model_dump(exclude={"password"})


def register(data: RegisterIn) -> tuple[User, int, bool]:
    """Create the student account and its lead, or link a lead from an earlier chat.

    Returns (user, lead_id, linked_existing_lead). Raises EmailTaken if an account has this email.
    """
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(func.lower(User.email) == data.email)) is not None:
            log_event(actor=data.email, event_type="register", tool_name="auth.register", input=_public_input(data),
                      output={"ok": False, "reason": "email_taken"}, reasoning_step=None, request_id=None)
            raise EmailTaken(data.email)

        user = User(email=data.email, full_name=f"{data.first_name} {data.last_name}", role="student",
                    password_hash=hash_password(data.password), is_active=True)
        db.add(user)
        try:
            db.flush()
        except IntegrityError:          # a second request with the same email won the race
            db.rollback()
            raise EmailTaken(data.email)

        lead = db.scalars(select(LeadRow).where(func.lower(LeadRow.email) == data.email, LeadRow.user_id.is_(None))
                          .order_by(LeadRow.id)).first()
        linked = lead is not None
        if lead is None:
            lead = LeadRow(channel="web", status="new")
            db.add(lead)
        lead.user_id = user.id
        lead.name = user.full_name
        lead.email = data.email
        lead.phone = f"{data.country_code} {data.phone}"
        lead.state = data.state
        lead.city = data.city
        lead.program_interest = data.course
        lead.lateral_entry = data.lateral_entry
        lead.contact_consent = True
        lead.consent_at = now
        db.commit()
        db.refresh(user)
        lead_id = lead.id
        db.expunge(user)

    log_event(actor=data.email, event_type="register", tool_name="auth.register", input=_public_input(data),
              output={"ok": True, "user_id": user.id, "lead_id": lead_id, "linked_existing_lead": linked},
              reasoning_step=None, request_id=None, lead_id=lead_id)
    return user, lead_id, linked
