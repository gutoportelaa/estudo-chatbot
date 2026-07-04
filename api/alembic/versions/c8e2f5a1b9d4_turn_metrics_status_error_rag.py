"""turn_metrics: status, error e rag_tokens (dashboard de Consumo)

Revision ID: c8e2f5a1b9d4
Revises: b7d1e6f3a9c2
Create Date: 2026-07-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8e2f5a1b9d4'
down_revision: Union[str, Sequence[str], None] = 'b7d1e6f3a9c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'turn_metrics',
        sa.Column('status', sa.String(length=16), nullable=False, server_default='ok'),
    )
    op.add_column('turn_metrics', sa.Column('error', sa.String(length=300), nullable=True))
    op.add_column(
        'turn_metrics',
        sa.Column('rag_tokens', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('turn_metrics', 'rag_tokens')
    op.drop_column('turn_metrics', 'error')
    op.drop_column('turn_metrics', 'status')
