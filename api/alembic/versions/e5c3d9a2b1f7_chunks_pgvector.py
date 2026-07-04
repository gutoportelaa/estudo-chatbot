"""habilita pgvector e cria a tabela chunks (RAG, issue #34)

Revision ID: e5c3d9a2b1f7
Revises: d4f2a1b7c9e3
Create Date: 2026-07-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'e5c3d9a2b1f7'
down_revision: Union[str, Sequence[str], None] = 'd4f2a1b7c9e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        'chunks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('document_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        # Dimensionless: aceita qualquer provedor de embeddings.
        sa.Column('embedding', Vector(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chunks_document_id', 'chunks', ['document_id'])
    op.create_index('ix_chunks_user_id', 'chunks', ['user_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_chunks_user_id', table_name='chunks')
    op.drop_index('ix_chunks_document_id', table_name='chunks')
    op.drop_table('chunks')
    # A extensão é deixada instalada (pode haver outros usos).
