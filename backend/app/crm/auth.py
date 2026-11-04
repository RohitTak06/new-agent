"""Authentication and role checks (JWT bearer tokens). Enforced on the server for every route.

Roles: admin, counsellor, student. Every request reloads the user, so deactivating
an account or changing a role takes effect at once. Logins and denials are audited.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy import select

from app.crm.db.base import SessionLocal
from app.crm.db.models import Lead as LeadRow
from app.crm.db.models import User
from app.crm.service import hash_password, log_event, verify_password

JWT_ALGORITHM = "HS256"
TOKEN_HOURS = 8
MIN_SECRET_LENGTH = 32
STAFF = ("counsellor", "admin")
_PLACEHOLDER_SECRETS = {"", "change-me"}
# Verified when the email is unknown, so response time doesn't reveal which accounts exist.
_DUMMY_HASH = hash_password("not-a-real-password")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/crm/auth/login", auto_error=False)


class CurrentUser(BaseModel):
    """The authenticated caller. lead_id is the student's own lead, if any."""

    id: int
    email: str
    full_name: str
    role: str
    lead_id: Optional[int] = None

    @property
    def is_staff(self) -> bool:
        return self.role in STAFF


def _secret() -> str:
    """The signing key. Fails closed on a missing, placeholder or short secret."""
    secret = os.getenv("JWT_SECRET", "")
    if secret in _PLACEHOLDER_SECRETS or len(secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(f"Set JWT_SECRET in .env to a random value of at least {MIN_SECRET_LENGTH} characters")
    return secret


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def create_token(user_id: int, role: str, hours: float = TOKEN_HOURS) -> str:
    """Sign a token for this user. `hours` may be negative in tests."""
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "role": role, "iat": now, "exp": now + timedelta(hours=hours)},
                      _secret(), algorithm=JWT_ALGORITHM)


def authenticate(email: str, password: str) -> Optional[User]:
    """Return the active user for these credentials, else None. Audits every attempt, never the password."""
    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == email)).first()
    valid = verify_password(password, user.password_hash if user else _DUMMY_HASH)
    ok = bool(user and valid and user.is_active)
    log_event(actor=email[:255], event_type="login", tool_name="auth.login", input={"email": email[:255]},
              output={"ok": ok}, reasoning_step=None, request_id=None)
    return user if ok else None


def _load_user(user_id: int) -> Optional[CurrentUser]:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            return None
        lead_id = db.scalar(select(LeadRow.id).where(LeadRow.user_id == user.id))
        return CurrentUser(id=user.id, email=user.email, full_name=user.full_name, role=user.role, lead_id=lead_id)


def optional_user(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[CurrentUser]:
    """The caller, or None without a token. A bad token is always a 401, never 'anonymous'."""
    if token is None:
        return None
    try:
        claims = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]})
        user = _load_user(int(claims["sub"]))
    except (jwt.InvalidTokenError, ValueError):
        raise _unauthorized("Invalid or expired token")
    if user is None:
        raise _unauthorized("Account not active")
    return user


def current_user(user: Optional[CurrentUser] = Depends(optional_user)) -> CurrentUser:
    """Require a logged-in caller (401 otherwise)."""
    if user is None:
        raise _unauthorized()
    return user


def deny(user: CurrentUser, request: Request, reason: str) -> HTTPException:
    """Audit a refused request and return the 403 to raise."""
    log_event(actor=user.email, event_type="access_denied", tool_name=request.url.path,
              input={"method": request.method, "role": user.role}, output=None,
              reasoning_step=reason, request_id=None)
    return HTTPException(status_code=403, detail="Not allowed")


def require_role(*roles: str) -> Callable[..., CurrentUser]:
    """Dependency factory: the caller must have one of these roles."""
    def check(request: Request, user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if user.role not in roles:
            raise deny(user, request, f"requires role {'/'.join(roles)}")
        return user
    return check


require_staff = require_role(*STAFF)
require_admin = require_role("admin")


def ensure_lead_access(user: CurrentUser, lead_id: int, request: Request) -> None:
    """Staff may touch any lead; a student only their own. Same 403 whether or not the lead exists."""
    if not user.is_staff and user.lead_id != lead_id:
        raise deny(user, request, f"lead {lead_id} is not this student's lead")


def require_lead_access(lead_id: int, request: Request, user: CurrentUser = Depends(current_user)) -> CurrentUser:
    """Dependency for routes with a {lead_id} path parameter."""
    ensure_lead_access(user, lead_id, request)
    return user


def audit_action(user: CurrentUser, action: str, input: Optional[dict], output: Optional[dict],
                 lead_id: Optional[int] = None) -> None:
    """Record who did a state change through the API (service logs don't know the user)."""
    log_event(actor=user.email, event_type="api_action", tool_name=action, input=input, output=output,
              reasoning_step=None, request_id=None, lead_id=lead_id)
