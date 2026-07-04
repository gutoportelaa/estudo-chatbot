"""chunks.page — página de origem do chunk no PDF (citações de RAG por página)

Revision ID: e1b4c7f9a2d6
Revises: d9a3f1c7e2b5
Create Date: 2026-07-03 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1b4c7f9a2d6'
down_revision: Union[str, Sequence[str], None] = 'd9a3f1c7e2b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('chunks', sa.Column('page', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chunks', 'page')
