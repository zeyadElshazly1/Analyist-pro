"""
Database connection and session management.

Uses SQLite by default (zero-config, file-backed, survives restarts).
Set DATABASE_URL env var (or .env file) to switch to PostgreSQL for production:
  DATABASE_URL=postgresql+psycopg2://user:pass@localhost/analyistpro
"""
import os
from pathlib import Path

# Load .env from the api root (one level above this file's parent directory)
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_env_path, override=False)
except ImportError:
    pass

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./analyistpro.db",  # Default: SQLite in api root
)

# SQLite needs check_same_thread=False for FastAPI's async context
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,      # Detect stale connections
    echo=False,              # Set True for SQL query logging in dev
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session and closes it after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Apply all pending Alembic migrations at startup (upgrade head).

    This replaces the old ``Base.metadata.create_all()`` call so the live
    database is always in sync with the migration history.  On the very
    first run against a blank database Alembic will create every table
    from scratch; on subsequent startups it only applies new migrations.

    If Alembic is unavailable or the migration directory is missing
    (e.g. running tests against an in-memory SQLite), we fall back to
    ``create_all`` so tests keep working without a full migration stack.
    """
    import logging
    _log = logging.getLogger(__name__)

    try:
        from alembic.config import Config
        from alembic import command
        import pathlib

        # Locate alembic.ini relative to this file: apps/api/alembic.ini
        alembic_ini = pathlib.Path(__file__).resolve().parent.parent / "alembic.ini"
        if not alembic_ini.exists():
            raise FileNotFoundError(f"alembic.ini not found at {alembic_ini}")

        alembic_cfg = Config(str(alembic_ini))
        # Override sqlalchemy.url with the runtime DATABASE_URL so the same
        # config works in every environment without editing alembic.ini.
        alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)

        _log.info("Running Alembic migrations (upgrade head)…")
        command.upgrade(alembic_cfg, "head")
        _log.info("Alembic migrations complete")

    except Exception as exc:
        _log.warning(
            f"Alembic migration failed ({exc}); falling back to create_all. "
            "This is normal in tests — in production ensure alembic.ini is present."
        )
        from app import models  # noqa: F401
        Base.metadata.create_all(bind=engine)
