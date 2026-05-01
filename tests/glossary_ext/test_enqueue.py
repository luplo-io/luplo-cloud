import pytest

from luplo_cloud.glossary_ext.enqueue import enqueue_extract_for_item


@pytest.mark.asyncio
async def test_enqueue_extract_for_item_creates_pending_job(oss_conn, seed_project):
    job_id = await enqueue_extract_for_item(
        oss_conn, item_id="item-123", project_id=seed_project,
    )
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT job_type, status, kv FROM jobs WHERE id = %s", (job_id,)
        )
        row = await cur.fetchone()
    assert row[0] == "glossary.extract"
    assert row[1] == "pending"
    assert row[2]["item_id"] == "item-123"
    assert row[2]["project_id"] == seed_project


@pytest.mark.asyncio
async def test_enqueue_extract_for_item_dedupes_per_item(oss_conn, seed_project):
    j1 = await enqueue_extract_for_item(
        oss_conn, item_id="item-456", project_id=seed_project,
    )
    j2 = await enqueue_extract_for_item(
        oss_conn, item_id="item-456", project_id=seed_project,
    )
    assert j1 == j2
