"""
Alembic migration environment.
Loads the sync DB URL from environment / .env and wires
all ORM models so autogenerate can detect schema changes.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ── Path setup — ensure repo root is on sys.path ─────────────────────────────
repo_root = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(repo_root))

from dotenv import load_dotenv

load_dotenv(repo_root / "backend" / ".env")
load_dotenv(repo_root / ".env")

# ── Import all models so Alembic sees them for autogenerate ──────────────────
from backend.app.db.base import Base
from backend.app.models import application, candidate, consent, job, user  # noqa: F401

# ── Alembic config object ─────────────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url with env var
sync_url = os.environ.get(
    "SYNC_DATABASE_URL",
    "postgresql+psycopg2://arp:arp_password@localhost:5432/arp_db",
)
config.set_main_option("sqlalchemy.url", sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ── Offline mode ──────────────────────────────────────────────────────────────


def run_migrations_offline() -> None:
    """Generate SQL script without connecting to DB."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode ───────────────────────────────────────────────────────────────


def run_migrations_online() -> None:
    """Apply migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
