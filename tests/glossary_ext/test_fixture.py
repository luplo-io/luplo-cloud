import pytest


@pytest.mark.asyncio
async def test_oss_db_conn_fixture(oss_conn):
    async with oss_conn.cursor() as cur:
        await cur.execute("SELECT 1")
        row = await cur.fetchone()
        assert row[0] == 1


@pytest.mark.asyncio
async def test_seed_group_inserts_through_full_chain(seed_group):
    # If we got here without exceptions, all three seed fixtures (project, actor, group)
    # successfully inserted against the live schema. seed_group returns the new gid.
    assert seed_group.startswith("grp-")
