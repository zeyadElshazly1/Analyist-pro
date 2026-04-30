"""add audit_log enrichment columns (severity, category, user_agent)

Revision ID: a1b2c3d4e5f6
Revises: 369725030118
Create Date: 2026-04-30

Adds the three columns written by the upgraded audit logging service that
were not present in the initial schema migration:

  severity   VARCHAR(16)  NULL  — low / medium / high / critical
  category   VARCHAR(32)  NULL  — data_access / auth / export / …
  user_agent VARCHAR(256) NULL  — HTTP User-Agent string

All columns are nullable so existing rows remain valid without a backfill.
Indexes mirror those on the ORM model (severity, category).
The migration is idempotent: it checks for the column before adding it so
that re-running against an already-migrated database is safe.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision = "369725030118"
branch_labels = None
depends_on = None


def _existing_columns(table: str) -> set[str]:
    bind = op.get_bind()
    insp = inspect(bind)
    return {col["name"] for col in insp.get_columns(table)}


def upgrade() -> None:
    existing = _existing_columns("audit_logs")

    if "severity" not in existing:
        op.add_column("audit_logs", sa.Column("severity", sa.String(16), nullable=True))
        op.create_index("ix_audit_logs_severity", "audit_logs", ["severity"], unique=False)

    if "category" not in existing:
        op.add_column("audit_logs", sa.Column("category", sa.String(32), nullable=True))
        op.create_index("ix_audit_logs_category", "audit_logs", ["category"], unique=False)

    if "user_agent" not in existing:
        op.add_column("audit_logs", sa.Column("user_agent", sa.String(256), nullable=True))


def downgrade() -> None:
    existing = _existing_columns("audit_logs")

    if "user_agent" in existing:
        op.drop_column("audit_logs", "user_agent")

    if "category" in existing:
        op.drop_index("ix_audit_logs_category", table_name="audit_logs")
        op.drop_column("audit_logs", "category")

    if "severity" in existing:
        op.drop_index("ix_audit_logs_severity", table_name="audit_logs")
        op.drop_column("audit_logs", "severity")
