"""
Pytest fixtures shared across all tests.
Uses an in-memory SQLite database so tests are fully isolated from production.
"""
import base64
import hashlib
import hmac
import io
import json
import os
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Point to an in-memory DB and set a deterministic JWT secret before importing app
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SENTRY_DSN", "")  # disable Sentry in tests
TEST_JWT_SECRET = "test-jwt-secret-for-pytest-only"
os.environ["SUPABASE_JWT_SECRET"] = TEST_JWT_SECRET

from app.db import Base, get_db
from app.main import app

# ── In-memory test engine ─────────────────────────────────────────────────────
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

TEST_USER_ID = "00000000-0000-0000-0000-000000000001"
TEST_USER_EMAIL = "test@example.com"


def _make_test_jwt(user_id: str = TEST_USER_ID, email: str = TEST_USER_EMAIL) -> str:
    """Create a valid HS256 JWT signed with TEST_JWT_SECRET for use in tests."""
    secret = TEST_JWT_SECRET.encode()

    def b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64url(json.dumps({
        "sub": user_id,
        "email": email,
        "role": "authenticated",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
    }).encode())
    signing_input = f"{header}.{payload}".encode()
    sig = b64url(hmac.new(secret, signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function", autouse=True)
def setup_db(tmp_path, monkeypatch):
    """Create all tables fresh for each test, drop afterwards."""
    from app.state import PROJECT_FILES
    import app.config as cfg
    import app.routes.upload as upload_mod

    test_upload_dir = str(tmp_path / "uploads")
    os.makedirs(test_upload_dir, exist_ok=True)
    monkeypatch.setattr(cfg, "UPLOAD_DIR", test_upload_dir)
    monkeypatch.setattr(upload_mod, "UPLOAD_DIR", test_upload_dir)

    import app.db as db_mod
    monkeypatch.setattr(db_mod, "SessionLocal", TestingSessionLocal)

    # Bypass the JWKS client in tests (no network needed) so _decode_token falls
    # through to the HS256 path, which uses SUPABASE_JWT_SECRET from the env
    # (already set to TEST_JWT_SECRET above).
    import app.middleware.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_get_jwks_client", lambda: None)

    PROJECT_FILES.clear()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    PROJECT_FILES.clear()


@pytest.fixture(scope="function")
def client(setup_db):
    """FastAPI TestClient with DB dependency overridden to in-memory SQLite."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    """
    Return Authorization headers with a valid test JWT.
    The first authenticated API call will lazy-create the user in the DB.
    """
    token = _make_test_jwt()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def project(client, auth_headers):
    """Create a project and return its JSON."""
    r = client.post("/projects", json={"name": "Test Project"}, headers=auth_headers)
    assert r.status_code == 200, r.text
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
def uploaded_project(client, project, csv_bytes, auth_headers):
    """Project with a CSV already uploaded. Returns project dict."""
    pid = project["id"]
    r = client.post(
        "/upload",
        files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"project_id": str(pid)},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    return project
