"""DAO for `glossary_suggestions` — lease, list, batch save, expire.

Lease model
-----------
A `lps glossary suggest` session calls `lease_suggestions` once with the
session actor id; the function flips up to `limit` available rows to
"reserved by me". Concurrent sessions (different actor) cannot see those
rows for the next `stale_after_minutes` minutes. The session keeps
decisions in memory and calls `apply_decisions` at save time.

`apply_decisions` runs inside the caller's transaction so the whole
batch is atomic. Each decision dispatches to the appropriate write —
'alias'/'canonical_replace'/'sibling'/'create' write to OSS glossary
tables; 'reject' writes a glossary_rejections row; 'skip' just releases
the lease without consuming the suggestion.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row

_RETURNING_COLS = (
    " RETURNING s.id, s.kind, s.candidate_surface, s.candidate_normalized,"
    "          s.target_group_id, s.similarity, s.source_item_id,"
    "          s.context_snippet, s.extracted_by_model, s.extracted_at"
)


async def lease_suggestions(
    conn: AsyncConnection[Any],
    *,
    project_id: str,
    leased_by: str,
    limit: int,
    stale_after_minutes: int,
    kind: str | None = None,
    min_similarity: float | None = None,
) -> list[dict[str, Any]]:
    """Atomically reserve up to `limit` available suggestions for the actor.

    Two-pass design: pass 1 hits the partial index `idx_suggestions_available`
    (consumed_at IS NULL AND reserved_at IS NULL) for the common easy path;
    pass 2 reclaims rows whose lease has gone stale. Splitting avoids the
    OR-clause that prevents the planner from using the partial index.

    Filters (`kind`, `min_similarity`) are pushed into the SQL so other
    sessions remain free to lease rows that don't match these filters.
    """
    common_filters = ["s.project_id = %(p)s", "s.consumed_at IS NULL"]
    params: dict[str, Any] = {"p": project_id, "by": leased_by, "lim": limit}
    if kind is not None:
        common_filters.append("s.kind = %(kind)s")
        params["kind"] = kind
    if min_similarity is not None:
        # term suggestions have NULL similarity; allow them through unless
        # caller explicitly limited to kind='pair'.
        common_filters.append(
            "(s.similarity IS NULL OR s.similarity >= %(sim)s)"
        )
        params["sim"] = min_similarity

    where_easy = " AND ".join([*common_filters, "s.reserved_at IS NULL"])
    where_stale = " AND ".join([
        *common_filters,
        "s.reserved_at IS NOT NULL",
        "s.reserved_at < now() - make_interval(mins => %(stale)s)",
    ])
    params["stale"] = stale_after_minutes

    async def _claim(where: str, remaining: int) -> list[dict[str, Any]]:
        if remaining <= 0:
            return []
        local = dict(params)
        local["lim"] = remaining
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "WITH cte AS ("
                f"  SELECT s.id FROM glossary_suggestions s"
                f"  WHERE {where}"
                f"  ORDER BY s.similarity DESC NULLS LAST, s.extracted_at ASC"
                f"  LIMIT %(lim)s"
                f"  FOR UPDATE SKIP LOCKED"
                ")"
                " UPDATE glossary_suggestions s"
                " SET reserved_by = %(by)s, reserved_at = now()"
                " FROM cte WHERE s.id = cte.id"
                + _RETURNING_COLS,
                local,
            )
            return list(await cur.fetchall())

    rows = await _claim(where_easy, limit)
    rows += await _claim(where_stale, limit - len(rows))
    return rows


async def release_lease(
    conn: AsyncConnection[Any],
    *,
    leased_by: str,
    suggestion_ids: Iterable[str] | None = None,
) -> int:
    """Release the lease (set reserved_by/at to NULL). Returns row count."""
    if suggestion_ids is None:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE glossary_suggestions"
                " SET reserved_by = NULL, reserved_at = NULL"
                " WHERE reserved_by = %(by)s AND consumed_at IS NULL",
                {"by": leased_by},
            )
            return cur.rowcount
    ids = list(suggestion_ids)
    if not ids:
        return 0
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE glossary_suggestions"
            " SET reserved_by = NULL, reserved_at = NULL"
            " WHERE reserved_by = %(by)s AND id = ANY(%(ids)s)"
            "   AND consumed_at IS NULL",
            {"by": leased_by, "ids": ids},
        )
        return cur.rowcount


_VALID_DECISIONS = {"alias", "canonical_replace", "sibling", "create", "reject", "skip"}


async def apply_decisions(
    conn: AsyncConnection[Any],
    *,
    actor_id: str,  # must be a UUID-formatted string (actors.id is UUID in OSS)
    decisions: list[dict[str, Any]],
) -> dict[str, int]:
    """Apply a batch of decisions atomically (inside caller's transaction).

    Each `decision` dict supports:
      - suggestion_id: required
      - decision: one of `_VALID_DECISIONS`
      - reason: required for `canonical_replace`; optional otherwise
      - new_canonical: optional for `create` (defaults to candidate_surface)
    Returns a summary like {"alias": 7, "canonical_replace": 1, ...}.
    """
    summary: dict[str, int] = {k: 0 for k in _VALID_DECISIONS}

    for d in decisions:
        sid = d["suggestion_id"]
        decision = d["decision"]
        if decision not in _VALID_DECISIONS:
            raise ValueError(f"Invalid decision: {decision!r}")

        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT id, project_id, kind, candidate_surface, candidate_normalized,"
                "       target_group_id, source_item_id, context_snippet"
                " FROM glossary_suggestions WHERE id = %s",
                (sid,),
            )
            row = await cur.fetchone()
        if row is None:
            raise ValueError(f"Suggestion {sid} not found")

        if decision == "skip":
            await conn.execute(
                "UPDATE glossary_suggestions"
                " SET reserved_by = NULL, reserved_at = NULL"
                " WHERE id = %s",
                (sid,),
            )
            summary["skip"] += 1
            continue

        # Each branch sets `affected_group_id` — the group on which the
        # tail-end suggestion_consumed history event should be audited.
        # None means the tail skips (orphan term reject — see Fix C).
        affected_group_id: str | None = None

        if decision == "alias":
            if not row["target_group_id"]:
                raise ValueError(
                    f"Suggestion {sid}: 'alias' requires target_group_id"
                )
            term_id = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO glossary_terms"
                " (id, group_id, surface, normalized, status,"
                "  source_item_id, context_snippet, decided_by, decided_at)"
                " VALUES (%s, %s, %s, %s, 'alias', %s, %s, %s, now())",
                (term_id, row["target_group_id"],
                 row["candidate_surface"], row["candidate_normalized"],
                 row["source_item_id"], row["context_snippet"], actor_id),
            )
            affected_group_id = row["target_group_id"]
        elif decision == "canonical_replace":
            if not row["target_group_id"]:
                raise ValueError(
                    f"Suggestion {sid}: 'canonical_replace' requires target_group_id"
                )
            reason = d.get("reason")
            if not reason:
                raise ValueError(
                    f"Suggestion {sid}: 'canonical_replace' requires a reason"
                )
            # Demote existing canonical to alias, capturing the old surface
            # for the canonical_changed history row.
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "UPDATE glossary_terms SET status = 'alias',"
                    "       decided_by = %s, decided_at = now()"
                    " WHERE group_id = %s AND status = 'canonical'"
                    " RETURNING surface",
                    (actor_id, row["target_group_id"]),
                )
                demoted = await cur.fetchone()
            old_canonical = demoted["surface"] if demoted else None
            # Insert new canonical
            term_id = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO glossary_terms"
                " (id, group_id, surface, normalized, status,"
                "  source_item_id, context_snippet, decided_by, decided_at)"
                " VALUES (%s, %s, %s, %s, 'canonical', %s, %s, %s, now())",
                (term_id, row["target_group_id"],
                 row["candidate_surface"], row["candidate_normalized"],
                 row["source_item_id"], row["context_snippet"], actor_id),
            )
            # Update group canonical
            await conn.execute(
                "UPDATE glossary_groups SET canonical = %s,"
                "       last_reviewed_by = %s, last_reviewed_at = now()"
                " WHERE id = %s",
                (row["candidate_surface"], actor_id, row["target_group_id"]),
            )
            await _record_history(
                conn,
                group_id=row["target_group_id"],
                action="canonical_changed",
                old_value={"canonical": old_canonical} if old_canonical else None,
                new_value={"canonical": row["candidate_surface"]},
                changed_by=actor_id,
                reason=reason,
            )
            affected_group_id = row["target_group_id"]
        elif decision == "sibling":
            if not row["target_group_id"]:
                raise ValueError(
                    f"Suggestion {sid}: 'sibling' requires target_group_id"
                )
            new_group_id = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO glossary_groups (id, project_id, scope, canonical, created_by)"
                " VALUES (%s, %s, 'project', %s, %s)",
                (new_group_id, row["project_id"], row["candidate_surface"], actor_id),
            )
            new_term_id = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO glossary_terms"
                " (id, group_id, surface, normalized, status, decided_by, decided_at)"
                " VALUES (%s, %s, %s, %s, 'canonical', %s, now())",
                (new_term_id, new_group_id, row["candidate_surface"],
                 row["candidate_normalized"], actor_id),
            )
            a, b = (
                (new_group_id, row["target_group_id"])
                if new_group_id < row["target_group_id"]
                else (row["target_group_id"], new_group_id)
            )
            await conn.execute(
                "INSERT INTO glossary_group_relations"
                " (id, project_id, group_a_id, group_b_id, relation,"
                "  registered_by, reason)"
                " VALUES (%s, %s, %s, %s, 'sibling', %s, %s)",
                (str(uuid.uuid4()), row["project_id"], a, b,
                 actor_id, d.get("reason")),
            )
            await _record_history(
                conn,
                group_id=row["target_group_id"],
                action="sibling_added",
                new_value={"sibling_group_id": new_group_id},
                changed_by=actor_id,
                reason=d.get("reason"),
            )
            affected_group_id = row["target_group_id"]
        elif decision == "create":
            new_group_id = str(uuid.uuid4())
            canonical = d.get("new_canonical") or row["candidate_surface"]
            await conn.execute(
                "INSERT INTO glossary_groups (id, project_id, scope, canonical, created_by)"
                " VALUES (%s, %s, 'project', %s, %s)",
                (new_group_id, row["project_id"], canonical, actor_id),
            )
            await conn.execute(
                "INSERT INTO glossary_terms"
                " (id, group_id, surface, normalized, status, decided_by, decided_at)"
                " VALUES (%s, %s, %s, %s, 'canonical', %s, now())",
                (str(uuid.uuid4()), new_group_id, canonical,
                 canonical.lower(), actor_id),
            )
            await _record_history(
                conn,
                group_id=new_group_id,
                action="group_created",
                new_value={"canonical": canonical},
                changed_by=actor_id,
            )
            # Audit link belongs on the new group, not the (possibly-set)
            # target_group_id from the suggestion. The tail below handles it.
            affected_group_id = new_group_id
        elif decision == "reject":
            if not row["target_group_id"]:
                # Orphan term reject — `glossary_rejections` requires NOT NULL
                # `group_id`. The consumed suggestion row itself is the
                # rejection record; SEAM contract requires workers to dedup
                # against consumed rows. See docs/SEAM-glossary-ext.md.
                affected_group_id = None
            else:
                await conn.execute(
                    "INSERT INTO glossary_rejections"
                    " (group_id, rejected_term, rejected_by, reason)"
                    " VALUES (%s, %s, %s, %s)"
                    " ON CONFLICT (group_id, rejected_term) DO NOTHING",
                    (row["target_group_id"], row["candidate_surface"],
                     actor_id, d.get("reason")),
                )
                await _record_history(
                    conn,
                    group_id=row["target_group_id"],
                    action="rejection_added",
                    new_value={"rejected_term": row["candidate_surface"]},
                    changed_by=actor_id,
                    reason=d.get("reason"),
                )
                affected_group_id = row["target_group_id"]

        # Mark suggestion consumed (skip path already returned)
        await conn.execute(
            "UPDATE glossary_suggestions"
            " SET consumed_at = now(), consumed_decision = %s"
            " WHERE id = %s",
            (decision, sid),
        )
        if affected_group_id is not None:
            await _record_history(
                conn,
                group_id=affected_group_id,
                action="suggestion_consumed",
                new_value={"suggestion_id": sid, "decision": decision},
                changed_by=actor_id,
            )
        summary[decision] += 1

    return summary


async def _record_history(
    conn: AsyncConnection[Any],
    *,
    group_id: str,
    action: str,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    changed_by: str | None = None,
    reason: str | None = None,
) -> None:
    await conn.execute(
        "INSERT INTO glossary_history"
        " (id, group_id, action, old_value, new_value, changed_by, reason)"
        " VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)",
        (
            str(uuid.uuid4()), group_id, action,
            None if old_value is None else json.dumps(old_value),
            None if new_value is None else json.dumps(new_value),
            changed_by, reason,
        ),
    )
