"""Logged-in students for tests.

Chatting needs a login, so a test that used to chat as a new anonymous visitor now chats as a
new student account. Like that visitor, the account has no lead until its first message. A test
that continues a conversation by session_id gets the same student back.
"""
from __future__ import annotations

import uuid

from app.crm.auth import create_token
from app.crm.db.base import SessionLocal
from app.crm.db.models import User
from app.crm.service import hash_password

_HASH = hash_password("student-test-password")   # hashed once: hashing is deliberately slow
_BY_SESSION: dict[str, dict] = {}


def fresh_student_headers() -> dict:
    """Auth headers for a brand-new student account with no lead yet."""
    tag = uuid.uuid4().hex[:10]
    with SessionLocal() as db:
        user = User(email=f"student-{tag}@example.test", full_name=f"Student {tag}", role="student",
                    password_hash=_HASH, is_active=True)
        db.add(user)
        db.commit()
        user_id = user.id
    return {"Authorization": f"Bearer {create_token(user_id, 'student')}"}


def headers_for(headers: dict | None, body: dict) -> dict:
    """The caller's own headers; else the student who owns this session_id; else a new student."""
    if headers is not None:
        return headers
    return _BY_SESSION.get(body.get("session_id") or "") or fresh_student_headers()


def remember(session_id: str | None, headers: dict) -> None:
    """Keep who owns a session, so a later turn in it continues as the same student."""
    if session_id:
        _BY_SESSION[session_id] = headers
