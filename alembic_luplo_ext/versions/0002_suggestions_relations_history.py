"""glossary-ext 0002 — suggestions queue + group relations + history."""
from __future__ import annotations

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ── glossary_suggestions ─────────────────────────────────────
    op.execute("""
        CREATE TABLE glossary_suggestions (
            id                  TEXT PRIMARY KEY,
            project_id          TEXT NOT NULL REFERENCES projects(id),
            kind                TEXT NOT NULL CHECK (kind IN ('pair','term')),
            candidate_surface   TEXT NOT NULL,
            candidate_normalized TEXT NOT NULL,
            target_group_id     TEXT REFERENCES glossary_groups(id),
            similarity          DOUBLE PRECISION,
            source_item_id      TEXT REFERENCES items(id),
            context_snippet     TEXT,
            extracted_by_model  TEXT NOT NULL,
            extracted_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            reserved_by         UUID REFERENCES actors(id),
            reserved_at         TIMESTAMPTZ,
            consumed_at         TIMESTAMPTZ,
            consumed_decision   TEXT CHECK (consumed_decision IN
                                ('alias','canonical_replace','sibling','create','reject'))
        )
    """)
    op.execute("""
        CREATE INDEX idx_suggestions_available
            ON glossary_suggestions(project_id, kind, similarity DESC NULLS LAST)
            WHERE consumed_at IS NULL AND reserved_at IS NULL
    """)
    op.execute("""
        CREATE INDEX idx_suggestions_leased
            ON glossary_suggestions(reserved_by, reserved_at)
            WHERE reserved_at IS NOT NULL AND consumed_at IS NULL
    """)

    # ── glossary_group_relations ─────────────────────────────────
    op.execute("""
        CREATE TABLE glossary_group_relations (
            id            TEXT PRIMARY KEY,
            project_id    TEXT NOT NULL REFERENCES projects(id),
            group_a_id    TEXT NOT NULL REFERENCES glossary_groups(id),
            group_b_id    TEXT NOT NULL REFERENCES glossary_groups(id),
            relation      TEXT NOT NULL CHECK (relation IN ('sibling','related')),
            registered_by UUID REFERENCES actors(id),
            registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            reason        TEXT,
            CHECK (group_a_id < group_b_id),
            UNIQUE (group_a_id, group_b_id, relation)
        )
    """)
    op.execute(
        "CREATE INDEX idx_group_relations_a ON glossary_group_relations(group_a_id)"
    )
    op.execute(
        "CREATE INDEX idx_group_relations_b ON glossary_group_relations(group_b_id)"
    )

    # ── glossary_history ─────────────────────────────────────────
    op.execute("""
        CREATE TABLE glossary_history (
            id          TEXT PRIMARY KEY,
            group_id    TEXT NOT NULL REFERENCES glossary_groups(id),
            action      TEXT NOT NULL CHECK (action IN (
                            'group_created',
                            'canonical_changed',
                            'term_added',
                            'sibling_added',
                            'rejection_added',
                            'suggestion_consumed'
                        )),
            old_value   JSONB,
            new_value   JSONB,
            changed_by  UUID REFERENCES actors(id),
            changed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            reason      TEXT
        )
    """)
    op.execute("CREATE INDEX idx_glossary_history_group ON glossary_history(group_id)")
    op.execute(
        "CREATE INDEX idx_glossary_history_time ON glossary_history(changed_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS glossary_history CASCADE")
    op.execute("DROP TABLE IF EXISTS glossary_group_relations CASCADE")
    op.execute("DROP TABLE IF EXISTS glossary_suggestions CASCADE")
