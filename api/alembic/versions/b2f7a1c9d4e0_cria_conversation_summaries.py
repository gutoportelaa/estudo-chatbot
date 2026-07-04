"""cria tabela conversation_summaries (gestão de histórico)

Revision ID: b2f7a1c9d4e0
Revises: e311d14f419e
Create Date: 2026-06-21 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2f7a1c9d4e0'
down_revision: Union[str, Sequence[str], None] = 'e311d14f419e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'conversation_summaries',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('covered_message_count', sa.Integer(), nullable=False),
        sa.Column('source_message_count', sa.Integer(), nullable=False),
        sa.Column('summary_tokens', sa.Integer(), nullable=False),
        sa.Column('trigger', sa.String(length=32), nullable=False),
        sa.Column('model', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_conversation_summaries_session_id',
        'conversation_summaries',
        ['session_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_conversation_summaries_session_id', table_name='conversation_summaries')
    op.drop_table('conversation_summaries')
