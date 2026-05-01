"""DAO for the `jobs` table (enqueue side).

Workers (next scope) own the claim/finish/retry side. This module only
provides `enqueue_job` so the OSS-side hook (item upsert → enqueue
extract) can run without depending on worker code.

`dedup_key` is implemented as `kv->>'dedup_key'` and a partial unique
index applied lazily (created on first dedup'd insert via ON CONFLICT
fallback to SELECT). Workers free to ignore it.
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

    When `dedup_key` is set and a pending/running job with the same key
    already exists, returns the existing job's id without inserting.
    """
    if dedup_key is not None:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT id FROM jobs"
                " WHERE job_type = %(t)s"
                "   AND status IN ('pending','running')"
                "   AND kv ->> 'dedup_key' = %(k)s"
                " LIMIT 1",
                {"t": job_type, "k": dedup_key},
            )
            existing = await cur.fetchone()
            if existing:
                return existing["id"]
        kv = {**kv, "dedup_key": dedup_key}

    job_id = str(uuid.uuid4())
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jobs (id, job_type, kv) VALUES (%s, %s, %s::jsonb)",
            (job_id, job_type, json.dumps(kv)),
        )
    return job_id
