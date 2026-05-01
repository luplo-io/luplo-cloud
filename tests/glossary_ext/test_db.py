import os

import pytest

from luplo_cloud.glossary_ext.db import async_engine_factory


@pytest.mark.asyncio
async def test_engine_factory_returns_working_engine():
    url = (
        os.environ.get("LUPLO_EXT_TEST_DB_URL")
        or os.environ.get("LUPLO_TEST_DB_URL")
        or "postgresql://postgres:localdb@localhost:5433/luplo_test"
    )
    engine = async_engine_factory(url)
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
    finally:
        await engine.dispose()
