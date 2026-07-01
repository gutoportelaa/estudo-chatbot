"""proveniência do embedding em chunks (provider/model) — RAG re-vetorização

Revision ID: f1a7b3c2d8e9
Revises: e5c3d9a2b1f7
Create Date: 2026-07-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a7b3c2d8e9'
down_revision: Union[str, Sequence[str], None] = 'e5c3d9a2b1f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'chunks',
        sa.Column('embedding_provider', sa.String(length=32), nullable=False, server_default=''),
    )
    op.add_column(
        'chunks',
        sa.Column('embedding_model', sa.String(length=128), nullable=False, server_default=''),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chunks', 'embedding_model')
    op.drop_column('chunks', 'embedding_provider')
