import pytest


@pytest.mark.asyncio
async def test_jobs_table_exists(oss_conn):
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT 1 FROM information_schema.tables"
            " WHERE table_schema = 'public' AND table_name = 'jobs'"
        )
        assert await cur.fetchone() is not None


@pytest.mark.asyncio
async def test_jobs_columns(oss_conn):
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = 'jobs' ORDER BY ordinal_position"
        )
        cols = [r[0] for r in await cur.fetchall()]
    expected = {
        "id", "job_type", "status", "fail_count", "fail_reason",
        "status_changed_at", "kv", "created_at", "updated_at",
    }
    assert expected.issubset(set(cols))


@pytest.mark.asyncio
async def test_glossary_term_embeddings_exists(oss_conn):
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT 1 FROM information_schema.tables"
            " WHERE table_schema = 'public' AND table_name = 'glossary_term_embeddings'"
        )
        assert await cur.fetchone() is not None
