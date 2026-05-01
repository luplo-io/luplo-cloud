from pathlib import Path


def test_env_py_targets_luplo_ext_version_table():
    env_path = Path(__file__).resolve().parents[2] / "alembic_luplo_ext" / "env.py"
    assert env_path.exists(), "alembic_luplo_ext/env.py must exist"
    text = env_path.read_text(encoding="utf-8")
    assert 'version_table="luplo_ext_alembic_version"' in text
    assert "LUPLO_DB_URL" in text or "LUPLO_EXT_DB_URL" in text
