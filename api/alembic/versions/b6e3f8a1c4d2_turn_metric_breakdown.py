"""turn_metrics: breakdown de tokens por bloco (inspector sempre-on #31/D)

Revision ID: b6e3f8a1c4d2
Revises: a4d7e9c2f5b8
Create Date: 2026-07-06 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6e3f8a1c4d2'
down_revision: Union[str, Sequence[str], None] = 'a4d7e9c2f5b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    for col in ('tokens_system', 'tokens_summary', 'tokens_recent', 'tokens_tool'):
        op.add_column('turn_metrics', sa.Column(col, sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    for col in ('tokens_tool', 'tokens_recent', 'tokens_summary', 'tokens_system'):
        op.drop_column('turn_metrics', col)
