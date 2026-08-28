"""add stripe subscription fields to organizations

Revision ID: 9d5a798800b8
Revises: 002df4995e73
Create Date: 2026-07-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '9d5a798800b8'
down_revision: Union[str, None] = '002df4995e73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('organizations', sa.Column('stripe_customer_id', sa.String(length=255), nullable=True))
    op.add_column('organizations', sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True))
    op.add_column('organizations', sa.Column('subscription_status', sa.String(length=64), nullable=True))
    op.create_unique_constraint('uq_organizations_stripe_customer_id', 'organizations', ['stripe_customer_id'])
    op.create_unique_constraint('uq_organizations_stripe_subscription_id', 'organizations', ['stripe_subscription_id'])


def downgrade() -> None:
    op.drop_constraint('uq_organizations_stripe_subscription_id', 'organizations', type_='unique')
    op.drop_constraint('uq_organizations_stripe_customer_id', 'organizations', type_='unique')
    op.drop_column('organizations', 'subscription_status')
    op.drop_column('organizations', 'stripe_subscription_id')
    op.drop_column('organizations', 'stripe_customer_id')
