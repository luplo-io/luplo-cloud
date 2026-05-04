"""decks-ext 0005 — decks, deck_slides, deck_shares.

Three SaaS-extension tables on the OSS DB partition. FKs to existing OSS
tables (`projects`, `items`, `actors`) are written as raw SQL because the
OSS tables are TEXT PKs (see luplo `_db_assets/migrations/0001_init_schema`),
not uuids — id columns here mirror that convention so app-side
``str(uuid.uuid4())`` insert values keep working uniformly.

Backs the Chunk D Deck Hub feature in luplo-cloud SaaS. Schema lives here
(not in luplo-cloud/api/alembic) because the FKs cross into OSS tables;
the SaaS alembic chain runs against a separate DB in dev/test.
"""
from __future__ import annotations

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE decks (
            id                 TEXT PRIMARY KEY,
            project_id         TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title              TEXT NOT NULL,
            description        TEXT,
            status             TEXT NOT NULL DEFAULT 'draft'
                               CHECK (status IN ('draft','published','archived')),
            source_provenance  TEXT,
            source_format      TEXT NOT NULL DEFAULT 'marp-md',
            raw_content        TEXT NOT NULL,
            created_by         UUID NOT NULL REFERENCES actors(id),
            created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX decks_project_idx ON decks(project_id, status)")

    op.execute("""
        CREATE TABLE deck_slides (
            id          TEXT PRIMARY KEY,
            deck_id     TEXT NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
            position    INTEGER NOT NULL,
            kind        TEXT NOT NULL
                        CHECK (kind IN ('title','section','item','custom')),
            item_id     TEXT REFERENCES items(id) ON DELETE SET NULL,
            custom_md   TEXT,
            CONSTRAINT slide_kind_content_check CHECK (
                (kind = 'item' AND item_id IS NOT NULL AND custom_md IS NULL)
                OR (kind <> 'item' AND custom_md IS NOT NULL AND item_id IS NULL)
            ),
            UNIQUE (deck_id, position)
        )
    """)
    op.execute("CREATE INDEX deck_slides_deck_idx ON deck_slides(deck_id, position)")

    op.execute("""
        CREATE TABLE deck_shares (
            id          TEXT PRIMARY KEY,
            deck_id     TEXT NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
            token       TEXT NOT NULL UNIQUE,
            expires_at  TIMESTAMPTZ,
            revoked_at  TIMESTAMPTZ,
            created_by  UUID NOT NULL REFERENCES actors(id),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX deck_shares_active_token_idx
        ON deck_shares(token)
        WHERE revoked_at IS NULL
    """)


def downgrade() -> None:
    # Drop in reverse FK order so children disappear before parents.
    op.execute("DROP TABLE IF EXISTS deck_shares")
    op.execute("DROP TABLE IF EXISTS deck_slides")
    op.execute("DROP TABLE IF EXISTS decks")
