"""
JWT authentication middleware for FastAPI.
Verifies Supabase-issued JWTs — supports both the new ECC P-256 (ES256)
signing key and the legacy HS256 shared secret (for tokens issued before
Supabase rotated its JWT key).

Verification:
  - ES256/RS256 tokens use the Supabase JWKS endpoint selected by ``kid``.
  - Legacy HS256 tokens use SUPABASE_JWT_SECRET.

Users are lazy-created in our local DB on first authenticated request.
"""
import logging
import json
import os
import time
import urllib.error
import urllib.request
from typing import Optional

import jwt
from jwt import PyJWK
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.plan_names import PLAN_FREE

logger = logging.getLogger(__name__)

_ASYMMETRIC_ALGORITHMS = {"ES256", "RS256"}
_JWKS_CACHE_TTL_SECONDS = 300


class AuthServiceUnavailable(Exception):
    """Raised when auth infrastructure is unavailable, not when a token is bad."""


class AuthConfigError(AuthServiceUnavailable):
    """Raised when required auth config is missing."""

# ── Config helpers ────────────────────────────────────────────────────────────

def _supabase_url() -> str:
    """Read Supabase URL — supports both plain and NEXT_PUBLIC_ prefixed names."""
    url = (
        os.getenv("SUPABASE_URL")
        or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        or ""
    ).strip()
    return url.rstrip("/")


def _supabase_issuer() -> str:
    url = _supabase_url()
    if not url:
        raise AuthConfigError("SUPABASE_URL is not configured")
    return f"{url}/auth/v1"


def _jwks_uri() -> str:
    return f"{_supabase_issuer()}/.well-known/jwks.json"


_jwks_cache: Optional[dict] = None
_jwks_cache_expires_at = 0.0


def _fetch_jwks() -> dict:
    global _jwks_cache, _jwks_cache_expires_at

    now = time.time()
    if _jwks_cache is not None and now < _jwks_cache_expires_at:
        return _jwks_cache

    try:
        with urllib.request.urlopen(_jwks_uri(), timeout=5) as response:
            jwks = json.loads(response.read().decode("utf-8"))
    except AuthConfigError:
        raise
    except (OSError, urllib.error.URLError, ValueError) as exc:
        raise AuthServiceUnavailable("Could not fetch Supabase JWKS") from exc

    if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
        raise AuthServiceUnavailable("Supabase JWKS response was malformed")

    _jwks_cache = jwks
    _jwks_cache_expires_at = now + _JWKS_CACHE_TTL_SECONDS
    return jwks


def _get_jwk_for_kid(kid: str) -> PyJWK:
    for jwk in _fetch_jwks().get("keys", []):
        if jwk.get("kid") == kid:
            return PyJWK.from_dict(jwk)

    # Supabase can rotate keys; refresh once on a miss.
    global _jwks_cache, _jwks_cache_expires_at
    _jwks_cache = None
    _jwks_cache_expires_at = 0.0
    for jwk in _fetch_jwks().get("keys", []):
        if jwk.get("kid") == kid:
            return PyJWK.from_dict(jwk)

    raise jwt.InvalidTokenError("No matching JWKS key found for token kid")


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# ── JWT verification ──────────────────────────────────────────────────────────

def _decode_token(token: str) -> Optional[dict]:
    """
    Verify a Supabase JWT and return its payload, or None if invalid/expired.

    Dispatches by the token header algorithm so asymmetric Supabase tokens are
    verified with JWKS and legacy HS256 tokens still use SUPABASE_JWT_SECRET.
    """
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        logger.debug("JWT header parse failed: %s", exc)
        return None

    alg = header.get("alg")
    if alg == "HS256":
        try:
            secret = os.getenv("SUPABASE_JWT_SECRET", "")
            if not secret:
                raise AuthConfigError("SUPABASE_JWT_SECRET is not configured")
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
            if not isinstance(payload.get("sub"), str) or not payload["sub"]:
                logger.warning("HS256 JWT payload missing or invalid 'sub' claim")
                return None
            return payload
        except jwt.ExpiredSignatureError:
            logger.debug("JWT expired (HS256 path)")
            return None
        except jwt.PyJWTError as exc:
            logger.debug("JWT decode failed via HS256: %s", exc)
            return None

    if alg in _ASYMMETRIC_ALGORITHMS:
        try:
            kid = header.get("kid")
            if not isinstance(kid, str) or not kid:
                logger.warning("Asymmetric JWT missing kid header")
                return None
            signing_key = _get_jwk_for_kid(kid)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
                issuer=_supabase_issuer(),
            )
            if not isinstance(payload.get("sub"), str) or not payload["sub"]:
                logger.warning("JWT payload missing or invalid 'sub' claim")
                return None
            return payload
        except jwt.ExpiredSignatureError:
            logger.debug("JWT expired (%s JWKS path)", alg)
            return None
        except jwt.PyJWTError as exc:
            logger.debug("JWT decode failed via %s JWKS: %s", alg, exc)
            return None

    logger.warning("JWT rejected due to unsupported alg: %s", alg)

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
    metadata = payload.get("user_metadata")
    metadata_email = metadata.get("email") if isinstance(metadata, dict) else None
    email = payload.get("email") or metadata_email or f"{user_id}@supabase.local"

    user = db.query(User).filter(User.id == user_id).first()
    if user is not None:
        return user

    try:
        user = User(id=user_id, email=email, plan=PLAN_FREE)
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
            logger.warning("Local user create hit integrity conflict for %s", user_id[:8])
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not create user session for this account.",
                headers={"WWW-Authenticate": "Bearer"},
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
    try:
        payload = _decode_token(token)
    except AuthServiceUnavailable as exc:
        logger.warning("Auth verification unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable. Please try again.",
        ) from exc
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
    try:
        payload = _decode_token(token)
    except AuthServiceUnavailable:
        return None
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
    try:
        payload = _decode_token(token)
    except AuthServiceUnavailable:
        return None
    if payload is None:
        return None
    return _get_or_create_user(payload, db)
