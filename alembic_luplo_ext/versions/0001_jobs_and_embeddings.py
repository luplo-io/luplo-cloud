"""glossary-ext 0001 — jobs + glossary_term_embeddings.

Both tables live in the OSS luplo DB but are managed by the luplo-ext
alembic partition (version_table=luplo_ext_alembic_version). FKs to
existing OSS tables (projects, glossary_terms) are written as raw SQL
because OSS has no SQLAlchemy declarative metadata to import.

pgvector is REQUIRED for this scope (worker scope is OpenRouter-dependent
anyway, so we never deploy without it). Migration aborts loudly if the
extension is unavailable rather than creating a useless BYTEA column the
DAO would silently mis-cast.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from alembic.util.exc import CommandError

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def _require_pgvector() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
    ).fetchone()
    if row is None:
        raise CommandError(
            "pgvector is not available on this Postgres cluster "
            "(no entry in pg_available_extensions). Install the pgvector "
            "package on the Postgres host (e.g. `brew install pgvector`, "
            "`apt install postgresql-NN-pgvector`, or use the "
            "pgvector/pgvector docker image) before running glossary-ext "
            "alembic."
        )


def upgrade() -> None:
    _require_pgvector()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── jobs (generic queue, used by workers) ────────────────────
    op.execute("""
        CREATE TABLE jobs (
            id                TEXT PRIMARY KEY,
            job_type          TEXT NOT NULL,
            status            TEXT NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('pending','running','done','failed')),
            fail_count        INTEGER NOT NULL DEFAULT 0,
            fail_reason       TEXT,
            status_changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            kv                JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX idx_jobs_pending
            ON jobs(created_at)
            WHERE status = 'pending'
    """)
    op.execute("CREATE INDEX idx_jobs_type_status ON jobs(job_type, status)")

    # ── glossary_term_embeddings ─────────────────────────────────
    op.execute("""
        CREATE TABLE glossary_term_embeddings (
            id              TEXT PRIMARY KEY,
            project_id      TEXT NOT NULL REFERENCES projects(id),
            surface         TEXT NOT NULL,
            normalized      TEXT NOT NULL,
            model_id        TEXT NOT NULL,
            vector          VECTOR(1024),
            linked_term_id  TEXT REFERENCES glossary_terms(id),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (project_id, normalized, model_id)
        )
    """)
    op.execute(
        "CREATE INDEX idx_glossary_embeddings_project_normalized"
        " ON glossary_term_embeddings(project_id, normalized)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS glossary_term_embeddings CASCADE")
    op.execute("DROP TABLE IF EXISTS jobs CASCADE")
