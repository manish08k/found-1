"""add waiting to executionstatus enum (real fix)

Revision ID: 3fcc20e57bcc
Revises: 7dbaf66f9abc
Create Date: 2026-07-26 00:00:00.000000

Note: an earlier migration in this project's history is literally named
"add_waiting_status" but its upgrade()/downgrade() bodies are empty
no-ops — whoever wrote it relied on Base.metadata.create_all() picking
up the new enum value for fresh dev databases, which does NOT work for
an existing Postgres enum type in a real deployment (create_all only
creates missing tables, it doesn't ALTER an existing type). This
migration is the real fix, using the same ALTER TYPE ... ADD VALUE
pattern already proven to work for the OrgPlan 'business' tier
(migration 002df4995e73).
"""
from typing import Sequence, Union

from alembic import op

revision: str = '3fcc20e57bcc'
down_revision: Union[str, None] = '7dbaf66f9abc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE executionstatus ADD VALUE IF NOT EXISTS 'waiting' AFTER 'running'")


def downgrade() -> None:
    raise NotImplementedError(
        "Postgres has no ALTER TYPE ... DROP VALUE — removing 'waiting' requires a "
        "manual type rebuild (create new type, migrate the column, drop old type). "
        "Confirm no executions are in 'waiting' status before attempting it by hand."
    )
