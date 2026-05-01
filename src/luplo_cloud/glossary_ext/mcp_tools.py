"""Library functions wired into the SaaS MCP server.

Each function is the executable side of a confirmed natural-language
intent (the LLM-side conversion lives in the user's MCP client). The
SaaS MCP wrapper calls these after `require_project(project_id, "editor")`.
"""
from __future__ import annotations

import uuid
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from luplo_cloud.glossary_ext.dao_history import record_history
from luplo_cloud.glossary_ext.dao_relations import add_relation


async def _resolve_group(
    conn: AsyncConnection[Any], canonical_or_id: str, project_id: str | None,
) -> str | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id FROM glossary_groups WHERE id = %s", (canonical_or_id,)
        )
        row = await cur.fetchone()
        if row:
            return row[0]
        params: dict[str, Any] = {"c": canonical_or_id}
        sql_text = "SELECT id FROM glossary_groups WHERE canonical = %(c)s"
        if project_id:
            sql_text += " AND project_id = %(p)s"
            params["p"] = project_id
        await cur.execute(sql_text, params)
        row = await cur.fetchone()
        return row[0] if row else None


async def glossary_add_group(
    conn: AsyncConnection[Any],
    *,
    project_id: str,
    canonical: str,
    actor_id: str,
    definition: str | None = None,
) -> dict[str, Any]:
    existing = await _resolve_group(conn, canonical, project_id)
    if existing:
        return {"created": False, "group_id": existing,
                "reason": "canonical already exists in project"}
    group_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO glossary_groups"
        " (id, project_id, scope, canonical, definition, created_by)"
        " VALUES (%s, %s, 'project', %s, %s, %s)",
        (group_id, project_id, canonical, definition, actor_id),
    )
    await conn.execute(
        "INSERT INTO glossary_terms"
        " (id, group_id, surface, normalized, status, decided_by, decided_at)"
        " VALUES (%s, %s, %s, %s, 'canonical', %s, now())",
        (str(uuid.uuid4()), group_id, canonical, canonical.lower(), actor_id),
    )
    await record_history(
        conn, group_id=group_id, action="group_created",
        new_value={"canonical": canonical, "definition": definition},
        changed_by=actor_id,
    )
    return {"created": True, "group_id": group_id}


async def preview_glossary_link(
    conn: AsyncConnection[Any],
    *,
    canonical_or_group_id: str,
    alias_surface: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Pre-check before glossary_link — surfaces prior rejection."""
    group_id = await _resolve_group(conn, canonical_or_group_id, project_id)
    if not group_id:
        return {"previously_rejected": False,
                "group_id": None, "exists": False}
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT rejected_at, reason FROM glossary_rejections"
            " WHERE group_id = %s AND rejected_term = %s",
            (group_id, alias_surface),
        )
        row = await cur.fetchone()
    if row:
        return {
            "previously_rejected": True,
            "group_id": group_id,
            "exists": True,
            "rejection_reason": row["reason"],
            "rejected_at": row["rejected_at"].isoformat(),
        }
    return {"previously_rejected": False, "group_id": group_id, "exists": True}


async def glossary_link(
    conn: AsyncConnection[Any],
    *,
    canonical_or_group_id: str,
    alias_surface: str,
    actor_id: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    group_id = await _resolve_group(conn, canonical_or_group_id, project_id)
    if not group_id:
        return {"added": False, "reason": "group not found"}
    term_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO glossary_terms"
        " (id, group_id, surface, normalized, status, decided_by, decided_at)"
        " VALUES (%s, %s, %s, %s, 'alias', %s, now())",
        (term_id, group_id, alias_surface, alias_surface.lower(), actor_id),
    )
    await record_history(
        conn, group_id=group_id, action="term_added",
        new_value={"surface": alias_surface, "status": "alias"},
        changed_by=actor_id,
    )
    return {"added": True, "term_id": term_id, "group_id": group_id}


async def glossary_link_sibling(
    conn: AsyncConnection[Any],
    *,
    project_id: str,
    group_x_id: str,
    group_y_id: str,
    actor_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    rid = await add_relation(
        conn,
        project_id=project_id,
        group_x_id=group_x_id,
        group_y_id=group_y_id,
        relation="sibling",
        registered_by=actor_id,
        reason=reason,
    )
    await record_history(
        conn, group_id=group_x_id, action="sibling_added",
        new_value={"sibling_group_id": group_y_id, "relation_id": rid},
        changed_by=actor_id, reason=reason,
    )
    return {"added": True, "relation_id": rid}
