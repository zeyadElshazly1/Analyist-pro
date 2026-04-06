"""
JWT authentication middleware for FastAPI.
Uses stdlib hmac+base64 for HS256 to avoid cryptography dependency conflicts.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User

# ── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production-please").encode()
ACCESS_TOKEN_EXPIRE_SECONDS = 60 * 60 * 24 * 7  # 7 days
_HASH_ITERATIONS = 260_000

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# ── Password helpers (PBKDF2-SHA256, no bcrypt dependency) ───────────────────
def hash_password(password: str) -> str:
    """Return a stored hash string: 'pbkdf2$salt$hash'."""
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _HASH_ITERATIONS)
    return f"pbkdf2${salt}${h.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    try:
        _, salt, expected_hex = stored.split("$")
        h = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), _HASH_ITERATIONS)
        return hmac.compare_digest(h.hex(), expected_hex)
    except Exception:
        return False


# ── Minimal HS256 JWT ─────────────────────────────────────────────────────────
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_access_token(user_id: int) -> str:
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url_encode(json.dumps({
        "sub": str(user_id),
        "exp": int(time.time()) + ACCESS_TOKEN_EXPIRE_SECONDS,
    }).encode())
    signing_input = f"{header}.{payload}".encode()
    signature = _b64url_encode(hmac.new(SECRET_KEY, signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def _decode_token(token: str) -> Optional[int]:
    """Return user_id from token or None if invalid/expired."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload_b64, signature = parts
        signing_input = f"{header}.{payload_b64}".encode()
        expected_sig = _b64url_encode(hmac.new(SECRET_KEY, signing_input, hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected_sig):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return int(payload["sub"])
    except Exception:
        return None


# ── FastAPI dependencies ──────────────────────────────────────────────────────
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    user_id = _decode_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Returns the User if a valid token is provided, else None."""
    if not token:
        return None
    user_id = _decode_token(token)
    if user_id is None:
        return None
    return db.query(User).filter(User.id == user_id).first()
