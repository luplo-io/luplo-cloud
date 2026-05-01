"""DAO for `glossary_history` audit trail."""
from __future__ import annotations

import json
import uuid
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row


async def record_history(
    conn: AsyncConnection[Any],
    *,
    group_id: str,
    action: str,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    changed_by: str | None = None,
    reason: str | None = None,
) -> str:
    hid = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO glossary_history"
        " (id, group_id, action, old_value, new_value, changed_by, reason)"
        " VALUES (%(id)s, %(g)s, %(a)s, %(ov)s::jsonb, %(nv)s::jsonb, %(cb)s, %(r)s)",
        {
            "id": hid,
            "g": group_id,
            "a": action,
            "ov": None if old_value is None else json.dumps(old_value),
            "nv": None if new_value is None else json.dumps(new_value),
            "cb": changed_by,
            "r": reason,
        },
    )
    return hid


async def list_history_for_group(
    conn: AsyncConnection[Any],
    *,
    group_id: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT id, group_id, action, old_value, new_value,"
            "       changed_by, changed_at, reason"
            " FROM glossary_history"
            " WHERE group_id = %(g)s"
            " ORDER BY changed_at DESC LIMIT %(l)s",
            {"g": group_id, "l": limit},
        )
        return list(await cur.fetchall())
