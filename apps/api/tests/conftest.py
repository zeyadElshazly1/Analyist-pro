"""
Pytest fixtures shared across all tests.
Uses an in-memory SQLite database so tests are fully isolated from production.
"""
import io
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Point to an in-memory DB before importing anything from app
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SENTRY_DSN", "")  # disable Sentry in tests

from app.db import Base, get_db
from app.main import app

# ── In-memory test engine ─────────────────────────────────────────────────────
# StaticPool ensures all connections share the same in-memory database instance.
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function", autouse=True)
def setup_db(tmp_path, monkeypatch):
    """Create all tables fresh for each test, drop afterwards.
    Uses a per-test temp upload dir so disk-scan fallback in state.py
    never finds files from a different test run."""
    from app.state import PROJECT_FILES
    import app.config as cfg
    import app.routes.upload as upload_mod

    # Point uploads to a fresh temp directory for this test so the disk-scan
    # fallback in state.py never finds files from a different test.
    test_upload_dir = str(tmp_path / "uploads")
    os.makedirs(test_upload_dir, exist_ok=True)
    monkeypatch.setattr(cfg, "UPLOAD_DIR", test_upload_dir)
    monkeypatch.setattr(upload_mod, "UPLOAD_DIR", test_upload_dir)  # module-level copy

    # Patch SessionLocal at the db module level so all inline imports
    # (state.py, analysis_stream.py) get the test session factory
    import app.db as db_mod
    monkeypatch.setattr(db_mod, "SessionLocal", TestingSessionLocal)

    PROJECT_FILES.clear()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    PROJECT_FILES.clear()


@pytest.fixture(scope="function")
def client(setup_db):
    """FastAPI TestClient with DB dependency overridden to in-memory SQLite.
    setup_db already patches app.db.SessionLocal so all direct imports also get the test factory."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def project(client):
    """Create a project and return its JSON."""
    r = client.post("/projects", json={"name": "Test Project"})
    assert r.status_code == 200
    return r.json()


@pytest.fixture
def csv_bytes():
    """Minimal valid CSV as bytes."""
    return (
        b"name,age,salary\n"
        b"Alice,30,70000\n"
        b"Bob,25,55000\n"
        b"Carol,35,90000\n"
        b"Dave,28,62000\n"
        b"Eve,42,110000\n"
        b"Frank,31,75000\n"
        b"Grace,29,68000\n"
        b"Hank,38,85000\n"
        b"Ivy,26,58000\n"
        b"Jack,45,120000\n"
    )


@pytest.fixture
def uploaded_project(client, project, csv_bytes):
    """Project with a CSV already uploaded. Returns project dict."""
    pid = project["id"]
    r = client.post(
        "/upload",
        files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"project_id": str(pid)},
    )
    assert r.status_code == 200
    return project
