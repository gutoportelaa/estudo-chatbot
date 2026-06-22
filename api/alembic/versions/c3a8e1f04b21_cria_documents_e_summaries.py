"""cria tabelas documents, summaries e summary_documents (entrega final RF-TEC-002)

Revision ID: c3a8e1f04b21
Revises: b2f7a1c9d4e0
Create Date: 2026-06-22 03:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a8e1f04b21'
down_revision: Union[str, Sequence[str], None] = 'b2f7a1c9d4e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'documents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('content_type', sa.String(length=128), nullable=False),
        sa.Column('storage_backend', sa.String(length=16), nullable=False),
        sa.Column('storage_key', sa.String(length=512), nullable=False),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_documents_user_id', 'documents', ['user_id'])

    op.create_table(
        'summaries',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('llm_model', sa.String(length=128), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_summaries_user_id', 'summaries', ['user_id'])

    op.create_table(
        'summary_documents',
        sa.Column('summary_id', sa.String(length=36), nullable=False),
        sa.Column('document_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['summary_id'], ['summaries.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('summary_id', 'document_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('summary_documents')
    op.drop_index('ix_summaries_user_id', table_name='summaries')
    op.drop_table('summaries')
    op.drop_index('ix_documents_user_id', table_name='documents')
    op.drop_table('documents')
