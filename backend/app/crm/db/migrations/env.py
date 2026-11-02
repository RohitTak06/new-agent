"""Alembic migration environment for the CRM module.

Run migrations from the backend/ directory:

    cd backend
    alembic -c app/crm/db/alembic.ini upgrade head

DATABASE_URL must be set in the environment (via .env — never committed).
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Make `app` importable when alembic is invoked from backend/
# env.py location: backend/app/crm/db/migrations/env.py
#   parents[0] = migrations/
#   parents[1] = db/
#   parents[2] = crm/
#   parents[3] = app/
#   parents[4] = backend/   <-- added to sys.path
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from app.crm.db.base import Base  # noqa: E402
import app.crm.db.models  # noqa: F401, E402 — registers all models on Base.metadata

# ---------------------------------------------------------------------------
# Alembic config object
# ---------------------------------------------------------------------------
config = context.config

# Override sqlalchemy.url with DATABASE_URL so .env controls the target.
# The placeholder value in alembic.ini is never used.
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL to stdout)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
