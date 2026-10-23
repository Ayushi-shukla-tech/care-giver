"""add medicine is_active and cancelled reminder status

Revision ID: 65379183fbfa
Revises: 660c5f001474
Create Date: 2026-07-16 21:04:10.599413

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65379183fbfa'
down_revision: Union[str, Sequence[str], None] = '660c5f001474'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'medicines',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column('medicines', 'is_active', server_default=None)
    op.execute("ALTER TYPE remindereventstatus ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    """Downgrade schema."""
    # Note: Postgres does not support removing an enum value; downgrading
    # only reverses the is_active column addition.
    op.drop_column('medicines', 'is_active')
