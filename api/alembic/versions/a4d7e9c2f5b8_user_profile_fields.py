"""usuário: campos de perfil (nome, email, descrição, avatar) — B1/#39

Revision ID: a4d7e9c2f5b8
Revises: e1b4c7f9a2d6
Create Date: 2026-07-06 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4d7e9c2f5b8'
down_revision: Union[str, Sequence[str], None] = 'e1b4c7f9a2d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('full_name', sa.String(length=120), nullable=True))
    op.add_column('users', sa.Column('email', sa.String(length=160), nullable=True))
    op.add_column('users', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('avatar_key', sa.String(length=256), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'avatar_key')
    op.drop_column('users', 'description')
    op.drop_column('users', 'email')
    op.drop_column('users', 'full_name')
