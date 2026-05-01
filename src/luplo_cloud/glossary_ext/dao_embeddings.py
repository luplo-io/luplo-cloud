"""DAO for `glossary_term_embeddings`.

Workers populate this table with vectors from BGE-M3. This DAO provides
upsert + lookup helpers shared by workers and the suggestions DAO.
pgvector is required (migration 0001 enforces). Vectors are Python
lists of floats (length 1024 for BGE-M3) or None when caller is just
upserting metadata before the embed job lands.
"""
from __future__ import annotations

import uuid
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row


def _vec_literal(vector: list[float] | None) -> str | None:
    if vector is None:
        return None
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


async def upsert_embedding(
    conn: AsyncConnection[Any],
    *,
    project_id: str,
    surface: str,
    normalized: str,
    model_id: str,
    vector: list[float] | None,
    linked_term_id: str | None,
) -> str:
    """Upsert by (project_id, normalized, model_id). Returns the row id.

    The `vector` column is nullable; passing None is valid (writes NULL).
    The `::vector` cast tolerates NULL natively in Postgres so we use a
    single code path regardless of whether the embedding has been
    computed yet.
    """
    eid = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO glossary_term_embeddings"
        " (id, project_id, surface, normalized, model_id, vector, linked_term_id)"
        " VALUES (%(id)s, %(p)s, %(s)s, %(n)s, %(m)s, %(v)s::vector, %(t)s)"
        " ON CONFLICT (project_id, normalized, model_id) DO UPDATE"
        " SET surface = EXCLUDED.surface,"
        "     vector = COALESCE(EXCLUDED.vector, glossary_term_embeddings.vector),"
        "     linked_term_id = EXCLUDED.linked_term_id",
        {
            "id": eid, "p": project_id, "s": surface, "n": normalized,
            "m": model_id, "v": _vec_literal(vector), "t": linked_term_id,
        },
    )

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT id FROM glossary_term_embeddings"
            " WHERE project_id = %(p)s AND normalized = %(n)s AND model_id = %(m)s",
            {"p": project_id, "n": normalized, "m": model_id},
        )
        row = await cur.fetchone()
        assert row is not None
        return row["id"]


async def list_embeddings_for_normalized(
    conn: AsyncConnection[Any],
    *,
    project_id: str,
    normalized: str,
) -> list[dict[str, Any]]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT id, surface, normalized, model_id, linked_term_id"
            " FROM glossary_term_embeddings"
            " WHERE project_id = %(p)s AND normalized = %(n)s",
            {"p": project_id, "n": normalized},
        )
        return list(await cur.fetchall())
