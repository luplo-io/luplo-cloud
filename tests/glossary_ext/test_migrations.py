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


@pytest.mark.asyncio
async def test_glossary_suggestions_exists(oss_conn):
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = 'glossary_suggestions' ORDER BY ordinal_position"
        )
        cols = {r[0] for r in await cur.fetchall()}
    assert {"id", "project_id", "kind", "candidate_surface", "target_group_id",
            "similarity", "reserved_by", "reserved_at", "consumed_at",
            "consumed_decision"}.issubset(cols)


@pytest.mark.asyncio
async def test_glossary_group_relations_exists(oss_conn):
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = 'glossary_group_relations' ORDER BY ordinal_position"
        )
        cols = {r[0] for r in await cur.fetchall()}
    assert {"id", "project_id", "group_a_id", "group_b_id",
            "relation", "registered_by"}.issubset(cols)


@pytest.mark.asyncio
async def test_glossary_history_exists(oss_conn):
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = 'glossary_history' ORDER BY ordinal_position"
        )
        cols = {r[0] for r in await cur.fetchall()}
    assert {"id", "group_id", "action", "old_value", "new_value",
            "changed_by", "changed_at", "reason"}.issubset(cols)
