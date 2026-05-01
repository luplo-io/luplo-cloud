"""High-level enqueue helpers used by the SaaS API layer."""
from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

from luplo_cloud.glossary_ext.dao_jobs import enqueue_job


async def enqueue_extract_for_item(
    conn: AsyncConnection[Any],
    *,
    item_id: str,
    project_id: str,
) -> str:
    """Enqueue a `glossary.extract` job for the given item.

    Dedupes per item: re-enqueues for the same item collapse to the same
    pending row. Workers are free to debounce further (e.g. window
    multiple updates of the same item) but the seam guarantees no
    duplicate pending rows for the same item id.
    """
    return await enqueue_job(
        conn,
        job_type="glossary.extract",
        kv={"item_id": item_id, "project_id": project_id},
        dedup_key=f"extract:{item_id}",
    )
