"""merge migration heads

Revision ID: 369725030118
Revises: a4f8e2d1c9b3, f4a5b6c7d8e9
Create Date: 2026-04-29 22:17:33.579713

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '369725030118'
down_revision: Union[str, Sequence[str], None] = ('a4f8e2d1c9b3', 'f4a5b6c7d8e9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
