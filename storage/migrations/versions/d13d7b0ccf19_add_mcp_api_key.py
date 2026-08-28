"""add mcp_api_key to users

Revision ID: d13d7b0ccf19
Revises: 3fcc20e57bcc
Create Date: 2026-07-26 01:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd13d7b0ccf19'
down_revision: Union[str, None] = '3fcc20e57bcc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('mcp_api_key', sa.String(length=255), nullable=True))
    op.create_unique_constraint('uq_users_mcp_api_key', 'users', ['mcp_api_key'])


def downgrade() -> None:
    op.drop_constraint('uq_users_mcp_api_key', 'users', type_='unique')
    op.drop_column('users', 'mcp_api_key')
