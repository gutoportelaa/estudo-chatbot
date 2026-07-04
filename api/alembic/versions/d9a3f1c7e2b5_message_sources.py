"""messages.sources (citações estruturadas: busca web #35 e RAG #34)

Revision ID: d9a3f1c7e2b5
Revises: c8e2f5a1b9d4
Create Date: 2026-07-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9a3f1c7e2b5'
down_revision: Union[str, Sequence[str], None] = 'c8e2f5a1b9d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('messages', sa.Column('sources', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('messages', 'sources')
