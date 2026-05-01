"""glossary-ext 0003 — partial unique index for jobs dedup_key.

Closes the race in `enqueue_job` when two concurrent transactions both
miss the SELECT and both INSERT. The index lets the INSERT use
`ON CONFLICT DO NOTHING RETURNING id`, falling back to a SELECT when
the conflict fires. Filter on `status IN ('pending','running')` so a
completed/failed job doesn't block a fresh enqueue with the same key.
"""
from __future__ import annotations

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE UNIQUE INDEX uq_jobs_dedup_key_active
            ON jobs ((kv ->> 'dedup_key'), job_type)
            WHERE status IN ('pending','running')
              AND kv ? 'dedup_key'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_jobs_dedup_key_active")
