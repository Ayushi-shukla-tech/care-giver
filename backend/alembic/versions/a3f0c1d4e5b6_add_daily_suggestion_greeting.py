"""add daily suggestion greeting

Revision ID: a3f0c1d4e5b6
Revises: 608578c9d527
Create Date: 2026-07-18 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f0c1d4e5b6'
down_revision: Union[str, Sequence[str], None] = '608578c9d527'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('daily_suggestions', sa.Column('greeting', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('daily_suggestions', 'greeting')
