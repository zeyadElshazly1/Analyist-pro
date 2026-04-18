"""add prepared_datasets table

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-04-18

"""
from alembic import op
import sqlalchemy as sa


revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prepared_datasets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("stored_path", sa.String(512), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=True),
        sa.Column("columns", sa.Integer(), nullable=True),
        sa.Column("cleaning_meta_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prepared_datasets_id", "prepared_datasets", ["id"])
    op.create_index("ix_prepared_datasets_project_id", "prepared_datasets", ["project_id"])
    op.create_index("ix_prepared_datasets_file_hash", "prepared_datasets", ["file_hash"])


def downgrade() -> None:
    op.drop_index("ix_prepared_datasets_file_hash", table_name="prepared_datasets")
    op.drop_index("ix_prepared_datasets_project_id", table_name="prepared_datasets")
    op.drop_index("ix_prepared_datasets_id", table_name="prepared_datasets")
    op.drop_table("prepared_datasets")
