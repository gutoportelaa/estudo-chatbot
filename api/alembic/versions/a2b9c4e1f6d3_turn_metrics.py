"""tabela turn_metrics para a tela de Consumo (#37)

Revision ID: a2b9c4e1f6d3
Revises: f1a7b3c2d8e9
Create Date: 2026-07-01 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2b9c4e1f6d3'
down_revision: Union[str, Sequence[str], None] = 'f1a7b3c2d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'turn_metrics',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('model', sa.String(length=128), nullable=False),
        sa.Column('provider', sa.String(length=32), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False),
        sa.Column('output_tokens', sa.Integer(), nullable=False),
        sa.Column('latency_ms', sa.Float(), nullable=False),
        sa.Column('cost_usd', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_turn_metrics_user_id', 'turn_metrics', ['user_id'])
    op.create_index('ix_turn_metrics_session_id', 'turn_metrics', ['session_id'])
    op.create_index('ix_turn_metrics_created_at', 'turn_metrics', ['created_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_turn_metrics_created_at', table_name='turn_metrics')
    op.drop_index('ix_turn_metrics_session_id', table_name='turn_metrics')
    op.drop_index('ix_turn_metrics_user_id', table_name='turn_metrics')
    op.drop_table('turn_metrics')
