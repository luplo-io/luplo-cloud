"""DAO for the `jobs` table (enqueue side).

Workers (next scope) own the claim/finish/retry side. This module only
provides `enqueue_job` so the OSS-side hook (item upsert → enqueue
extract) can run without depending on worker code.

`dedup_key` is enforced at the DB layer by a partial unique index
(`uq_jobs_dedup_key_active`, see migration 0003) on
`(kv->>'dedup_key', job_type) WHERE status IN ('pending','running')`.
The INSERT uses `ON CONFLICT DO NOTHING RETURNING id`, falling back to
a SELECT when the conflict fires. This is concurrency-safe: two callers
with the same dedup_key in different transactions cannot create two
rows.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row


async def enqueue_job(
    conn: AsyncConnection[Any],
    *,
    job_type: str,
    kv: dict[str, Any],
    dedup_key: str | None = None,
) -> str:
    """Insert a pending job, returning its id.

    When `dedup_key` is set and a pending/running job with the same
    `(dedup_key, job_type)` already exists, returns the existing job's
    id without inserting. Concurrency-safe via the partial unique
    index `uq_jobs_dedup_key_active`.
    """
    if dedup_key is not None:
        kv = {**kv, "dedup_key": dedup_key}

    job_id = str(uuid.uuid4())
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "INSERT INTO jobs (id, job_type, kv) "
            "VALUES (%s, %s, %s::jsonb) "
            "ON CONFLICT DO NOTHING "
            "RETURNING id",
            (job_id, job_type, json.dumps(kv)),
        )
        row = await cur.fetchone()
        if row is not None:
            return row["id"]

        # Conflict fired — find the existing active row with this dedup_key.
        # Only reachable when dedup_key is set (no other unique constraint on jobs).
        await cur.execute(
            "SELECT id FROM jobs"
            " WHERE job_type = %(t)s"
            "   AND status IN ('pending','running')"
            "   AND kv ->> 'dedup_key' = %(k)s"
            " LIMIT 1",
            {"t": job_type, "k": dedup_key},
        )
        existing = await cur.fetchone()
        if existing is None:
            # Defensive: conflict fired but row already moved to done/failed.
            # Re-attempt insert (worker has finished the prior job, so it's
            # legitimate to enqueue a new one).
            await cur.execute(
                "INSERT INTO jobs (id, job_type, kv) "
                "VALUES (%s, %s, %s::jsonb) "
                "RETURNING id",
                (job_id, job_type, json.dumps(kv)),
            )
            existing = await cur.fetchone()
        return existing["id"]
