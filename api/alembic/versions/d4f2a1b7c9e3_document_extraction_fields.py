"""adiciona campos de extração de texto em documents (issue #33)

Revision ID: d4f2a1b7c9e3
Revises: c3a8e1f04b21
Create Date: 2026-06-30 20:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f2a1b7c9e3'
down_revision: Union[str, Sequence[str], None] = 'c3a8e1f04b21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default cobre as linhas já existentes; o default do modelo cuida
    # das novas. Mantido no schema por ser inofensivo e explícito.
    op.add_column(
        'documents',
        sa.Column(
            'extraction_status',
            sa.String(length=16),
            nullable=False,
            server_default='pending',
        ),
    )
    op.add_column(
        'documents',
        sa.Column('extracted_key', sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('documents', 'extracted_key')
    op.drop_column('documents', 'extraction_status')
