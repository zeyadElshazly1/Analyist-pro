"""add share_expires_at and share_revoked to analysis_results

Revision ID: c1d2e3f4a5b6
Revises: 3a7c91d2b445
Create Date: 2026-04-18

"""
from alembic import op
import sqlalchemy as sa


revision = "c1d2e3f4a5b6"
down_revision = "3a7c91d2b445"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analysis_results",
        sa.Column("share_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "analysis_results",
        sa.Column("share_revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("analysis_results", "share_revoked")
    op.drop_column("analysis_results", "share_expires_at")
