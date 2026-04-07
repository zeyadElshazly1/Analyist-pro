"""
JWT authentication middleware for FastAPI.
Verifies Supabase-issued JWTs — supports both the new ECC P-256 (ES256)
signing key and the legacy HS256 shared secret (for tokens issued before
Supabase rotated its JWT key).

Verification order:
  1. JWKS endpoint (ES256/RS256) — handles all new Supabase tokens
  2. Legacy HS256 shared secret — handles tokens issued before key rotation

Users are lazy-created in our local DB on first authenticated request.
"""
import logging
import os
from typing import Optional

import jwt
from jwt import PyJWKClient, PyJWKClientError
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User

logger = logging.getLogger(__name__)

# ── Config helpers ────────────────────────────────────────────────────────────

def _supabase_url() -> str:
    """Read Supabase URL — supports both plain and NEXT_PUBLIC_ prefixed names."""
    return (
        os.getenv("SUPABASE_URL")
        or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        or ""
    )


# Lazily-initialised JWKS client — fetches public keys from Supabase on first
# use and caches them.  One instance for the process lifetime.
_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> Optional[PyJWKClient]:
    global _jwks_client
    if _jwks_client is None:
        url = _supabase_url()
        if not url:
            return None
        jwks_uri = f"{url}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_uri, cache_keys=True)
    return _jwks_client


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# ── JWT verification ──────────────────────────────────────────────────────────

def _decode_token(token: str) -> Optional[dict]:
    """
    Verify a Supabase JWT and return its payload, or None if invalid/expired.

    Tries ES256/RS256 via JWKS first (Supabase default since key rotation),
    then falls back to legacy HS256 shared secret.
    """
    # ── Strategy 1: JWKS / asymmetric (ES256, RS256) ─────────────────────────
    try:
        client = _get_jwks_client()
        if client is not None:
            signing_key = client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                options={"verify_aud": False},  # Supabase aud varies by project
            )
            if not isinstance(payload.get("sub"), str) or not payload["sub"]:
                logger.warning("JWT payload missing or invalid 'sub' claim")
                return None
            return payload
    except PyJWKClientError as e:
        logger.debug(f"JWKS key lookup failed (will try HS256 fallback): {e}")
    except jwt.ExpiredSignatureError:
        logger.debug("JWT expired (JWKS path)")
        return None  # Expired — don't try HS256, the token is just expired
    except jwt.PyJWTError as e:
        logger.debug(f"JWT decode failed via JWKS: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error in JWKS verification: {e}")

    # ── Strategy 2: Legacy HS256 shared secret ────────────────────────────────
    try:
        secret = os.getenv("SUPABASE_JWT_SECRET", "")
        if secret:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            if not isinstance(payload.get("sub"), str) or not payload["sub"]:
                logger.warning("HS256 JWT payload missing or invalid 'sub' claim")
                return None
            return payload
    except jwt.ExpiredSignatureError:
        logger.debug("JWT expired (HS256 path)")
        return None
    except jwt.PyJWTError as e:
        logger.debug(f"JWT decode failed via HS256: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error in HS256 verification: {e}")

    return None


# ── User helper ───────────────────────────────────────────────────────────────

def _get_or_create_user(payload: dict, db: Session) -> User:
    """
    Look up user by Supabase UUID; create a local record if first login.

    Handles the race condition where two concurrent first-logins for the same
    user both attempt to INSERT — the second commit raises IntegrityError and
    we simply re-fetch the now-existing row.
    """
    user_id: str = payload["sub"]
    email: str = payload.get("email", "")

    user = db.query(User).filter(User.id == user_id).first()
    if user is not None:
        return user

    try:
        user = User(id=user_id, email=email, plan="free")
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created local user record for {user_id[:8]}…")
        return user
    except IntegrityError:
        # Another concurrent request already created the user — roll back and fetch
        db.rollback()
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            # Should never happen, but guard against it
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not create user session. Please try again.",
            )
        return user
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create user record for {user_id[:8]}…: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable. Please try again.",
        )


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
