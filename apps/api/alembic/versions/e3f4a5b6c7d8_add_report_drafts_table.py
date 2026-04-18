"""add report_drafts table

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-04-18

"""
from alembic import op
import sqlalchemy as sa


revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("analysis_result_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(512), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("selected_insight_ids_json", sa.Text(), nullable=True),
        sa.Column("selected_chart_ids_json", sa.Text(), nullable=True),
        sa.Column("template", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_result_id"], ["analysis_results.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_drafts_id", "report_drafts", ["id"])
    op.create_index("ix_report_drafts_project_id", "report_drafts", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_report_drafts_project_id", table_name="report_drafts")
    op.drop_index("ix_report_drafts_id", table_name="report_drafts")
    op.drop_table("report_drafts")
