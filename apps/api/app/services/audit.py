"""
Audit log service — records key user actions to the audit_logs table.

Usage (all existing call sites are unchanged):

    from app.services.audit import log_event
    log_event(db, action="upload",
              user_id="abc", resource_type="project", resource_id="42",
              detail={"filename": "sales.csv"}, ip_address=request.client.host)

Or with the enum taxonomy for new call sites:

    from app.services.audit import log_event, AuditAction
    log_event(db, action=AuditAction.EXPORT_REPORT, user_id=uid,
              resource_type="project", resource_id=str(pid),
              detail={"format": "xlsx"}, ip_address=ip)

All calls are fire-and-forget — the write is dispatched to a background
thread pool so the request path is never blocked.  Any DB failure is caught,
and after _FAIL_THRESHOLD consecutive failures the warning is escalated to
an ERROR log.
"""
from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog

logger = logging.getLogger(__name__)

# ── Thread pool (daemon threads so the process can exit cleanly) ──────────────
_EXECUTOR      = ThreadPoolExecutor(max_workers=2, thread_name_prefix="audit")
_fail_count    = 0
_fail_lock     = threading.Lock()
_FAIL_THRESHOLD = 5   # escalate from WARNING → ERROR after this many consecutive failures


# ── Event taxonomy ─────────────────────────────────────────────────────────────

class AuditAction(str, Enum):
    # Data actions
    UPLOAD_FILE    = "upload"
    DELETE_PROJECT = "delete_project"
    DELETE_ACCOUNT = "delete_account"
    EXPORT_REPORT  = "export_report"
    # Analysis
    RUN_ANALYSIS   = "analysis"
    RUN_AUTOML     = "run_automl"
    RUN_FORECAST   = "run_forecast"
    # Auth
    LOGIN_SUCCESS  = "login_success"
    LOGIN_FAILED   = "login_failed"
    # Admin
    ADMIN_CHANGE   = "admin_change"


class AuditSeverity(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class AuditCategory(str, Enum):
    DATA_ACCESS = "data_access"
    AUTH        = "auth"
    EXPORT      = "export"
    ANALYSIS    = "analysis"
    SECURITY    = "security"
    ADMIN       = "admin"


# Default severity + category inferred from action string
_ACTION_META: dict[str, tuple[AuditSeverity, AuditCategory]] = {
    "upload":         (AuditSeverity.LOW,    AuditCategory.DATA_ACCESS),
    "delete_project": (AuditSeverity.HIGH,   AuditCategory.DATA_ACCESS),
    "delete_account": (AuditSeverity.HIGH,   AuditCategory.AUTH),
    "export_report":  (AuditSeverity.MEDIUM, AuditCategory.EXPORT),
    "analysis":       (AuditSeverity.LOW,    AuditCategory.ANALYSIS),
    "run_automl":     (AuditSeverity.LOW,    AuditCategory.ANALYSIS),
    "run_forecast":   (AuditSeverity.LOW,    AuditCategory.ANALYSIS),
    "login_success":  (AuditSeverity.LOW,    AuditCategory.AUTH),
    "login_failed":   (AuditSeverity.MEDIUM, AuditCategory.SECURITY),
    "admin_change":   (AuditSeverity.HIGH,   AuditCategory.ADMIN),
}


# ── Public API ────────────────────────────────────────────────────────────────

def log_event(
    db: Session,
    *,
    action: str | AuditAction,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
    # New optional fields — all existing call sites need no changes
    severity: str | AuditSeverity | None = None,
    category: str | AuditCategory | None = None,
    user_agent: str | None = None,
    _sync: bool = False,   # True in tests for deterministic writes
) -> None:
    """
    Enqueue an audit event for background persistence.

    Never raises — if the write fails the error is logged (escalated to ERROR
    after _FAIL_THRESHOLD consecutive failures) and the caller is unaffected.

    The `db` parameter is retained for backward compatibility but is no longer
    used; the background writer opens its own short-lived session.
    """
    action_str = action.value if isinstance(action, AuditAction) else str(action)

    # Infer severity and category if not supplied
    meta = _ACTION_META.get(action_str, (AuditSeverity.LOW, AuditCategory.DATA_ACCESS))
    severity_val = str(severity) if severity is not None else meta[0].value
    category_val = str(category) if category is not None else meta[1].value

    kwargs: dict[str, Any] = dict(
        action=action_str,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        ip_address=ip_address,
        severity=severity_val,
        category=category_val,
        user_agent=user_agent,
    )

    if _sync:
        # Use the caller's session directly so tests can query it immediately after
        _write_event(_db=db, **kwargs)
    else:
        _EXECUTOR.submit(_write_event, _db=None, **kwargs)


# ── Background writer ─────────────────────────────────────────────────────────

def _write_event(
    *,
    _db: Session | None = None,   # None → create own session (production); provided → use it (tests)
    action: str,
    user_id: str | None,
    resource_type: str | None,
    resource_id: str | None,
    detail: dict[str, Any] | None,
    ip_address: str | None,
    severity: str,
    category: str,
    user_agent: str | None,
) -> None:
    """
    Write one audit entry.

    When `_db` is supplied (sync/test path) it is used directly and not closed
    afterward.  When `_db` is None (async/production path) a new short-lived
    session is created from the app session factory and closed on exit.
    """
    global _fail_count

    own_session = _db is None
    if own_session:
        from app.db import SessionLocal  # imported here to avoid circular import at module load
        db = SessionLocal()
    else:
        db = _db

    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=json.dumps(detail) if detail else None,
            ip_address=ip_address,
            severity=severity,
            category=category,
            user_agent=user_agent,
        )
        db.add(entry)
        db.commit()
        with _fail_lock:
            _fail_count = 0   # reset consecutive-failure streak on success
    except Exception as exc:  # noqa: BLE001
        with _fail_lock:
            _fail_count += 1
            count = _fail_count
        if count >= _FAIL_THRESHOLD:
            logger.error(
                "Audit logging has failed %d consecutive times (action=%s): %s",
                count, action, exc,
            )
        else:
            logger.warning("audit log failed (action=%s): %s", action, exc)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        if own_session:
            db.close()
