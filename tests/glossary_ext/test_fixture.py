import pytest


@pytest.mark.asyncio
async def test_oss_db_conn_fixture(oss_conn):
    async with oss_conn.cursor() as cur:
        await cur.execute("SELECT 1")
        row = await cur.fetchone()
        assert row[0] == 1
