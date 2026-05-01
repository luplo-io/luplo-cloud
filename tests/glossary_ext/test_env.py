from pathlib import Path


def test_env_py_targets_luplo_ext_version_table():
    env_path = Path(__file__).resolve().parents[2] / "alembic_luplo_ext" / "env.py"
    assert env_path.exists(), "alembic_luplo_ext/env.py must exist"
    text = env_path.read_text(encoding="utf-8")
    assert 'version_table="luplo_ext_alembic_version"' in text
    assert "LUPLO_DB_URL" in text or "LUPLO_EXT_DB_URL" in text


def test_env_py_strips_libpq_query_options():
    """asyncpg rejects libpq-style query params (e.g. ?sslmode=require);
    env.py must clear the URL query alongside the drivername coercion.
    """
    env_path = Path(__file__).resolve().parents[2] / "alembic_luplo_ext" / "env.py"
    text = env_path.read_text(encoding="utf-8")
    assert "query={}" in text, (
        "env.py must clear the URL query dict so libpq-style options "
        "(e.g. ?sslmode=require) don't reach asyncpg"
    )
