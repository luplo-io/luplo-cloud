"""glossary-ext 0004 — rename auto-named UNIQUE constraints to ORM names.

Migrations 0001/0002 created UNIQUE constraints inline, so Postgres
auto-named them (`<table>_<cols>_key`). The T7 ORM models named the
same constraints `uq_glossary_embedding_unique` and
`uq_group_relation_pair`. This migration brings the DB names in line
with the ORM so future `ON CONFLICT ON CONSTRAINT uq_*` clauses work.

Functional behavior is unchanged — column-list ON CONFLICT inference
already works for both before and after this rename.
"""
from __future__ import annotations

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE glossary_term_embeddings"
        " RENAME CONSTRAINT glossary_term_embeddings_project_id_normalized_model_id_key"
        " TO uq_glossary_embedding_unique"
    )
    op.execute(
        "ALTER TABLE glossary_group_relations"
        " RENAME CONSTRAINT glossary_group_relations_group_a_id_group_b_id_relation_key"
        " TO uq_group_relation_pair"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE glossary_group_relations"
        " RENAME CONSTRAINT uq_group_relation_pair"
        " TO glossary_group_relations_group_a_id_group_b_id_relation_key"
    )
    op.execute(
        "ALTER TABLE glossary_term_embeddings"
        " RENAME CONSTRAINT uq_glossary_embedding_unique"
        " TO glossary_term_embeddings_project_id_normalized_model_id_key"
    )
