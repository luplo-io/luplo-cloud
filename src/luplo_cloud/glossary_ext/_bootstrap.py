"""Idempotent bootstrap for the luplo-ext alembic partition.

The luplo-ext alembic uses version_table=`luplo_ext_alembic_version`.
On a fresh OSS DB, the first `alembic upgrade head` from luplo-ext will
create that table automatically. On databases that already had a
prior bootstrap attempt, this script no-ops. Kept as a hook for future
schema-rename migrations.
"""
from __future__ import annotations

import os
import sys

import psycopg
from sqlalchemy.engine.url import make_url


def _normalise(url: str) -> str:
    u = make_url(url).set(query={})
    if u.drivername.startswith("postgresql+"):
        u = u.set(drivername="postgresql")
    return u.render_as_string(hide_password=False)


def main() -> int:
    db_url = (
        os.environ.get("LUPLO_EXT_DB_URL") or os.environ.get("LUPLO_DB_URL")
    )
    if not db_url:
        print("[bootstrap-ext] LUPLO_EXT_DB_URL/LUPLO_DB_URL not set; skipping",
              file=sys.stderr)
        return 0
    with psycopg.connect(_normalise(db_url), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.tables"
            " WHERE table_schema = 'public' AND table_name = 'luplo_ext_alembic_version'"
        )
        exists = cur.fetchone() is not None
    print(f"[bootstrap-ext] partition table {'exists' if exists else 'absent'}; "
          "alembic upgrade will handle the rest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
