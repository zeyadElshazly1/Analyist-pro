"""
JWT authentication middleware for FastAPI.
Verifies Supabase-issued HS256 JWTs using SUPABASE_JWT_SECRET.
Users are lazy-created in our DB on first authenticated request.
"""
import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User

# ── Config ────────────────────────────────────────────────────────────────────
# Read lazily so the .env loaded by db.py is always available by the time
# a real request arrives, even if auth.py was imported before db.py ran load_dotenv.
def _get_secret_key() -> bytes:
    key = os.getenv("SUPABASE_JWT_SECRET", "")
    return key.encode()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# ── JWT helpers ───────────────────────────────────────────────────────────────
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _decode_token(token: str) -> Optional[dict]:
    """
    Verify a Supabase HS256 JWT and return its payload, or None if invalid/expired.
    Payload contains: sub (UUID), email, role, exp, aud, etc.
    """
    try:
        secret_key = _get_secret_key()
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload_b64, signature = parts
        signing_input = f"{header}.{payload_b64}".encode()
        expected_sig = _b64url_encode(
            hmac.new(secret_key, signing_input, hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected_sig):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def _get_or_create_user(payload: dict, db: Session) -> User:
    """Look up user by Supabase UUID; create a local record if first login."""
    user_id: str = payload["sub"]
    email: str = payload.get("email", "")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        user = User(id=user_id, email=email, plan="free")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# ── FastAPI dependencies ──────────────────────────────────────────────────────
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = _decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _get_or_create_user(payload, db)


def optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Returns the User if a valid token is provided, else None."""
    if not token:
        return None
    payload = _decode_token(token)
    if payload is None:
        return None
    return _get_or_create_user(payload, db)


def get_user_from_query_token(
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    For SSE endpoints where EventSource cannot send Authorization headers.
    Reads JWT from ?token= query parameter.
    """
    if not token:
        return None
    payload = _decode_token(token)
    if payload is None:
        return None
    return _get_or_create_user(payload, db)
