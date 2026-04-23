"""add run model fields to analysis_results

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-04-23

Extends AnalysisResult to be the canonical run anchor per RUN_MODEL_IMPLEMENTATION_SPEC.md.

All new columns are nullable or carry a server_default so existing rows remain valid:
  - status defaults to "report_ready" (all existing rows were successful completions)
  - started_at is NULL for historical rows (duration cannot be backfilled)
  - all other new columns are nullable

FK constraints for file_id and user_id are declared only in the ORM model, not via
ALTER TABLE, for SQLite compatibility in tests. Postgres enforces them through the
model-level ForeignKey definitions at table-creation time.
"""
from alembic import op
import sqlalchemy as sa


revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Run lifecycle
    op.add_column(
        "analysis_results",
        sa.Column("status", sa.String(32), nullable=False, server_default="report_ready"),
    )
    op.add_column(
        "analysis_results",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "analysis_results",
        sa.Column("trigger_source", sa.String(32), nullable=True),
    )
    op.add_column(
        "analysis_results",
        sa.Column("error_summary", sa.Text(), nullable=True),
    )

    # Source file link (FK enforced by ORM, not ALTER TABLE — SQLite compat)
    op.add_column(
        "analysis_results",
        sa.Column("file_id", sa.Integer(), nullable=True),
    )

    # Ownership (denormalized from project)
    op.add_column(
        "analysis_results",
        sa.Column("user_id", sa.String(36), nullable=True),
    )

    # AI model metadata
    op.add_column(
        "analysis_results",
        sa.Column("ai_model_version", sa.String(64), nullable=True),
    )

    # AI data-story payload (separate from main result_json)
    op.add_column(
        "analysis_results",
        sa.Column("story_result_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analysis_results", "story_result_json")
    op.drop_column("analysis_results", "ai_model_version")
    op.drop_column("analysis_results", "user_id")
    op.drop_column("analysis_results", "file_id")
    op.drop_column("analysis_results", "error_summary")
    op.drop_column("analysis_results", "trigger_source")
    op.drop_column("analysis_results", "started_at")
    op.drop_column("analysis_results", "status")
