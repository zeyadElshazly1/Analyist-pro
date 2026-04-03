"""
Database connection and session management.

Uses SQLite by default (zero-config, file-backed, survives restarts).
Set DATABASE_URL env var to switch to PostgreSQL for production:
  DATABASE_URL=postgresql+psycopg2://user:pass@localhost/analyistpro
"""
import os
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
    """Create all tables. Called at app startup."""
    from app import models  # noqa: F401 — ensures models are registered
    Base.metadata.create_all(bind=engine)
