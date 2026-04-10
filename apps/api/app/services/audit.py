"""
Audit log service — records key user actions to the audit_logs table.

Usage:
    from app.services.audit import log_event
    log_event(db, user_id="abc", action="upload",
              resource_type="project", resource_id=str(project_id),
              detail={"filename": "sales.csv"}, ip_address=request.client.host)

All calls are fire-and-forget — failures are silently swallowed so that
audit logging never disrupts the main request path.
"""
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog

logger = logging.getLogger(__name__)


def log_event(
    db: Session,
    *,
    action: str,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """
    Persist an audit event.  Never raises — any DB failure is caught and
    logged as a warning so the calling request path is unaffected.
    """
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=json.dumps(detail) if detail else None,
            ip_address=ip_address,
        )
        db.add(entry)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"audit log failed (action={action}): {exc}")
        db.rollback()
