"""SQLAlchemy engine, session factory, and declarative Base for the CRM module.

DATABASE_URL is read from the environment (never hardcoded — see RULES.md).
A fallback is provided for local dev convenience only; never commit .env.
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()  # repo-root .env; real env vars still win

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://buildathon:buildathon@localhost:5432/admissions",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Shared declarative base — all CRM models inherit from this."""


def get_session():
    """FastAPI dependency: yields a DB session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
