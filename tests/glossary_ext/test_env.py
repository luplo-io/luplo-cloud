from pathlib import Path


def test_env_py_targets_luplo_ext_version_table():
    env_path = Path(__file__).resolve().parents[2] / "alembic_luplo_ext" / "env.py"
    assert env_path.exists(), "alembic_luplo_ext/env.py must exist"
    text = env_path.read_text(encoding="utf-8")
    assert 'version_table="luplo_ext_alembic_version"' in text
    assert "LUPLO_DB_URL" in text or "LUPLO_EXT_DB_URL" in text


def test_env_py_uses_sync_psycopg_driver():
    """env.py uses sync psycopg3 (matches `lp migrate`'s libpq path so
    sslmode + tailnet hostnames work in prod). Async asyncpg was tried
    earlier but couldn't resolve the OSS DB hostname from the fly
    container during start.sh.
    """
    env_path = Path(__file__).resolve().parents[2] / "alembic_luplo_ext" / "env.py"
    text = env_path.read_text(encoding="utf-8")
    assert 'drivername="postgresql+psycopg"' in text
    # The async engine is gone; raw SQL migrations don't need it and
    # asyncpg's DSN/SSL/DNS path doesn't survive the prod tailnet path.
    assert "async_engine_from_config" not in text
    assert "from sqlalchemy.ext.asyncio" not in text
