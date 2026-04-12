"""add team_invites table

Revision ID: 3a7c91d2b445
Revises: 95df4ec3efa8
Create Date: 2026-04-12

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '3a7c91d2b445'
down_revision = '95df4ec3efa8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'team_invites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.String(length=36), nullable=False),
        sa.Column('member_id', sa.String(length=36), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['member_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_team_invites_id', 'team_invites', ['id'], unique=False)
    op.create_index('ix_team_invites_owner_id', 'team_invites', ['owner_id'], unique=False)
    op.create_index('ix_team_invites_member_id', 'team_invites', ['member_id'], unique=False)
    op.create_index('ix_team_invites_token', 'team_invites', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_team_invites_token', table_name='team_invites')
    op.drop_index('ix_team_invites_member_id', table_name='team_invites')
    op.drop_index('ix_team_invites_owner_id', table_name='team_invites')
    op.drop_index('ix_team_invites_id', table_name='team_invites')
    op.drop_table('team_invites')
