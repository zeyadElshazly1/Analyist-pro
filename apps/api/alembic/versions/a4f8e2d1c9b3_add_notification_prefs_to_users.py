"""add notification_prefs_json to users

Revision ID: a4f8e2d1c9b3
Revises: 3a7c91d2b445
Create Date: 2026-04-12

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a4f8e2d1c9b3'
down_revision = '3a7c91d2b445'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('notification_prefs_json', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'notification_prefs_json')
