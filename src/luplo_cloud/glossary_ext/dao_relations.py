"""DAO for `glossary_group_relations`.

Pair order is normalised so (a,b) and (b,a) collapse to the same row
(enforced by CHECK group_a_id < group_b_id). A UNIQUE constraint on
`(group_a_id, group_b_id, relation)` makes repeat inserts idempotent
at the DB layer; this DAO uses `ON CONFLICT (...) DO NOTHING RETURNING
id` so the dedup is concurrency-safe across transactions. The column-
list form lets Postgres infer the constraint regardless of the auto-
generated constraint name.
"""
from __future__ import annotations

import uuid
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row


async def add_relation(
    conn: AsyncConnection[Any],
    *,
    project_id: str,
    group_x_id: str,
    group_y_id: str,
    relation: str,
    registered_by: str | None,
    reason: str | None = None,
) -> str:
    """Add a relation between two groups. Returns row id (existing if duplicate)."""
    if group_x_id == group_y_id:
        raise ValueError("Cannot relate a group to itself")
    a, b = (group_x_id, group_y_id) if group_x_id < group_y_id else (group_y_id, group_x_id)

    rid = str(uuid.uuid4())
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "INSERT INTO glossary_group_relations"
            " (id, project_id, group_a_id, group_b_id, relation, registered_by, reason)"
            " VALUES (%(id)s, %(p)s, %(a)s, %(b)s, %(r)s, %(rb)s, %(reason)s)"
            " ON CONFLICT (group_a_id, group_b_id, relation) DO NOTHING"
            " RETURNING id",
            {
                "id": rid, "p": project_id, "a": a, "b": b,
                "r": relation, "rb": registered_by, "reason": reason,
            },
        )
        row = await cur.fetchone()
        if row is not None:
            return row["id"]

        # Conflict fired — fetch existing id.
        await cur.execute(
            "SELECT id FROM glossary_group_relations"
            " WHERE group_a_id = %(a)s AND group_b_id = %(b)s AND relation = %(r)s",
            {"a": a, "b": b, "r": relation},
        )
        existing = await cur.fetchone()
        if existing is None:
            raise RuntimeError(
                "ON CONFLICT fired but no matching row found — schema drift?"
            )
        return existing["id"]


async def list_relations_for_group(
    conn: AsyncConnection[Any],
    *,
    group_id: str,
) -> list[dict[str, Any]]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT id, project_id, group_a_id, group_b_id, relation,"
            "       registered_by, registered_at, reason"
            " FROM glossary_group_relations"
            " WHERE group_a_id = %(g)s OR group_b_id = %(g)s"
            " ORDER BY registered_at DESC",
            {"g": group_id},
        )
        return list(await cur.fetchall())
