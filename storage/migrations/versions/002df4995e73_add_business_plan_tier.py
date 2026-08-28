"""add business plan tier

Revision ID: 002df4995e73
Revises: 1a414ad31695
Create Date: 2026-07-20 00:00:00.000000

Adds 'business' to the orgplan Postgres enum, between 'pro' and
'enterprise' — matches the 5-tier plan table in core/plans.py.

Note: ALTER TYPE ... ADD VALUE is safe to run inside a normal
transactional migration on Postgres 12+ (the target version here — see
infra/terraform/aws/modules/database) as long as the new value isn't
also USED within that same migration/transaction, which it isn't here.
"""
from typing import Sequence, Union

from alembic import op

revision: str = '002df4995e73'
down_revision: Union[str, None] = '1a414ad31695'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE orgplan ADD VALUE IF NOT EXISTS 'business' AFTER 'pro'")


def downgrade() -> None:
    # Postgres has no ALTER TYPE ... DROP VALUE — removing an enum value
    # requires rebuilding the type (create new type, migrate the column,
    # drop old type). Not implemented here since it's a rare, disruptive
    # operation for a downgrade path; if you actually need to remove
    # 'business', first ensure no rows use it, then do the rebuild
    # manually rather than via a blind automated downgrade.
    raise NotImplementedError(
        "Downgrading the 'business' enum value requires a manual type "
        "rebuild — see this migration's comment. Confirm no organizations "
        "are on the business plan before attempting it."
    )
