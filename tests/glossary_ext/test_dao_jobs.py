import pytest

from luplo_cloud.glossary_ext.dao_jobs import enqueue_job


@pytest.mark.asyncio
async def test_enqueue_job_inserts_pending_row(oss_conn, seed_project):
    job_id = await enqueue_job(
        oss_conn,
        job_type="glossary.extract",
        kv={"item_id": "item-x", "project_id": seed_project},
    )
    assert isinstance(job_id, str)
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT job_type, status, kv FROM jobs WHERE id = %s", (job_id,)
        )
        row = await cur.fetchone()
    assert row[0] == "glossary.extract"
    assert row[1] == "pending"
    assert row[2]["item_id"] == "item-x"


@pytest.mark.asyncio
async def test_enqueue_job_dedupes_when_dedup_key_collides(oss_conn, seed_project):
    job_id_1 = await enqueue_job(
        oss_conn,
        job_type="glossary.extract",
        kv={"item_id": "item-y", "project_id": seed_project},
        dedup_key="extract:item-y",
    )
    job_id_2 = await enqueue_job(
        oss_conn,
        job_type="glossary.extract",
        kv={"item_id": "item-y", "project_id": seed_project},
        dedup_key="extract:item-y",
    )
    assert job_id_1 == job_id_2


@pytest.mark.asyncio
async def test_enqueue_job_does_not_dedup_across_job_types(oss_conn, seed_project):
    job_id_1 = await enqueue_job(
        oss_conn,
        job_type="glossary.extract",
        kv={"item_id": "item-z", "project_id": seed_project},
        dedup_key="shared-key",
    )
    job_id_2 = await enqueue_job(
        oss_conn,
        job_type="glossary.embed",
        kv={"item_id": "item-z", "project_id": seed_project},
        dedup_key="shared-key",
    )
    assert job_id_1 != job_id_2


@pytest.mark.asyncio
async def test_enqueue_job_does_not_dedup_after_completion(oss_conn, seed_project):
    job_id_1 = await enqueue_job(
        oss_conn,
        job_type="glossary.extract",
        kv={"item_id": "item-w", "project_id": seed_project},
        dedup_key="completed-key",
    )
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "UPDATE jobs SET status = 'done' WHERE id = %s", (job_id_1,)
        )
    job_id_2 = await enqueue_job(
        oss_conn,
        job_type="glossary.extract",
        kv={"item_id": "item-w", "project_id": seed_project},
        dedup_key="completed-key",
    )
    assert job_id_1 != job_id_2


@pytest.mark.asyncio
async def test_enqueue_job_no_dedup_when_key_is_none(oss_conn, seed_project):
    job_id_1 = await enqueue_job(
        oss_conn,
        job_type="glossary.extract",
        kv={"item_id": "item-q", "project_id": seed_project},
    )
    job_id_2 = await enqueue_job(
        oss_conn,
        job_type="glossary.extract",
        kv={"item_id": "item-q", "project_id": seed_project},
    )
    assert job_id_1 != job_id_2
