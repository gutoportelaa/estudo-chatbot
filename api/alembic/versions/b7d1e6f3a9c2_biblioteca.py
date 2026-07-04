"""Biblioteca: capa do documento + escopo de documentos por sessão

Revision ID: b7d1e6f3a9c2
Revises: a2b9c4e1f6d3
Create Date: 2026-07-01 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d1e6f3a9c2'
down_revision: Union[str, Sequence[str], None] = 'a2b9c4e1f6d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('documents', sa.Column('thumbnail_key', sa.String(length=512), nullable=True))
    op.create_table(
        'session_documents',
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('document_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('session_id', 'document_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('session_documents')
    op.drop_column('documents', 'thumbnail_key')
