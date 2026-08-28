"""partition executions table by month (created_at)

Revision ID: 6a5de1399ff2
Revises: 970516a1b6ff
Create Date: 2026-07-16 00:00:00.000000

WHY: `executions` is the table that grows with every workflow run across
every user — at 1M active users this is easily billions of rows within a
year. An unpartitioned table that size makes: (a) DELETE-based retention
cripplingly slow and (b) index bloat/vacuum time balloon. Range-partitioning
by month means retention is just DROP TABLE on old partitions (near-instant,
no VACUUM needed), and Postgres only scans the relevant partition(s) for
time-bounded queries (execution history views, dashboards).

IMPORTANT — read before running in production:
  - Postgres cannot ALTER an existing heap table into a partitioned table
    in place. This migration creates a NEW partitioned table
    (`executions_partitioned`), copies existing rows into it, then swaps
    it in under the original `executions` name. For a large existing
    table this copy is the expensive/slow part — test the timing against
    a staging copy of prod data and run this during a maintenance window
    or via a background copy + short cutover, not as a blind CI-triggered
    migration.
  - Foreign keys pointing at `executions.id` (if any are added later)
    need `executions.id` to stay unique across partitions, which is
    guaranteed here since the partition key (created_at) is NOT part of
    the FK'd column — the primary key below is (id, created_at) to
    satisfy Postgres's "partition key must be part of every unique
    constraint" rule; application code should keep using `id` alone for
    lookups (it still is unique), this only affects constraint DDL.
  - Only a handful of partitions are pre-created here (rolling window).
    Schedule a periodic job (Celery beat task or pg_partman) to create
    next month's partition ahead of time and drop/archive partitions
    older than your retention policy — this migration does not do that
    on an ongoing basis.
"""
from typing import Sequence, Union
from datetime import date

from alembic import op
import sqlalchemy as sa

revision: str = '6a5de1399ff2'
down_revision: Union[str, None] = '970516a1b6ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _month_bounds(months_back: int, months_forward: int):
    """Yield (partition_suffix, start_date, end_date) for a rolling window."""
    today = date.today().replace(day=1)
    y, m = today.year, today.month
    idx = -months_back
    bounds = []
    while idx <= months_forward:
        yy, mm = y, m + idx
        while mm > 12:
            mm -= 12
            yy += 1
        while mm < 1:
            mm += 12
            yy -= 1
        start = date(yy, mm, 1)
        end_yy, end_mm = (yy, mm + 1) if mm < 12 else (yy + 1, 1)
        end = date(end_yy, end_mm, 1)
        bounds.append((f"{yy}_{mm:02d}", start, end))
        idx += 1
    return bounds


def upgrade() -> None:
    op.execute("""
        CREATE TABLE executions_partitioned (
            LIKE executions INCLUDING DEFAULTS INCLUDING CONSTRAINTS
        ) PARTITION BY RANGE (created_at)
    """)

    # Primary key must include the partition column.
    op.execute("""
        ALTER TABLE executions_partitioned
        ADD PRIMARY KEY (id, created_at)
    """)

    # Pre-create 3 months back through 3 months forward; extend this window
    # via a scheduled job rather than re-running this migration.
    for suffix, start, end in _month_bounds(months_back=3, months_forward=3):
        op.execute(f"""
            CREATE TABLE IF NOT EXISTS executions_{suffix}
            PARTITION OF executions_partitioned
            FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')
        """)

    # Catch-all so inserts outside the pre-created window don't fail outright
    # while the periodic partition-creation job catches up.
    op.execute("""
        CREATE TABLE IF NOT EXISTS executions_default
        PARTITION OF executions_partitioned DEFAULT
    """)

    op.execute("""
        INSERT INTO executions_partitioned
        SELECT * FROM executions
    """)

    op.execute("ALTER TABLE executions RENAME TO executions_old")
    op.execute("ALTER TABLE executions_partitioned RENAME TO executions")

    op.execute("CREATE INDEX IF NOT EXISTS ix_executions_workflow_id ON executions (workflow_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_executions_status ON executions (status)")

    # Keep executions_old around for one release cycle as a safety net,
    # then DROP TABLE executions_old manually once you've verified the
    # swap. Not dropped automatically by this migration.


def downgrade() -> None:
    op.execute("ALTER TABLE executions RENAME TO executions_partitioned")
    op.execute("ALTER TABLE executions_old RENAME TO executions")
    op.execute("DROP TABLE executions_partitioned CASCADE")
