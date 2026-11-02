"""CRM database package.

Exports the three things every other file in crm/ needs:
    Base        — the shared DeclarativeBase
    engine      — the SQLAlchemy engine
    get_session — FastAPI dependency for a DB session
"""
from app.crm.db.base import Base, engine, get_session  # noqa: F401

# Import all models so that Base.metadata is fully populated when
# alembic or create_all() is called.
import app.crm.db.models  # noqa: F401
