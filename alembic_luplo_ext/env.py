"""Alembic env for the luplo glossary extension partition.

Targets the OSS luplo Postgres DB (NOT the SaaS DB), but tracks revisions
in a dedicated `luplo_ext_alembic_version` table so OSS migrations
(`lp migrate`, default `alembic_version`) and the SaaS-DB partition
(`saas_alembic_version` in luplo-cloud/api) all stay independent.

DB URL: read from LUPLO_EXT_DB_URL (preferred) or fall back to LUPLO_DB_URL.
"""
from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_raw_url = os.environ.get("LUPLO_EXT_DB_URL") or os.environ.get("LUPLO_DB_URL")
if not _raw_url:
    raise RuntimeError(
        "LUPLO_EXT_DB_URL (or LUPLO_DB_URL) must be set for glossary-ext alembic"
    )

# Force async driver for online mode; alembic env.py will route both modes
# through this URL. For offline mode SQLAlchemy synchronous URL is fine.
_url = make_url(_raw_url)
if _url.drivername in ("postgresql", "postgres"):
    _url = _url.set(drivername="postgresql+asyncpg")
config.set_main_option("sqlalchemy.url", _url.render_as_string(hide_password=False))

target_metadata = None  # raw SQL migrations only


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table="luplo_ext_alembic_version",
        version_table_schema="public",
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table="luplo_ext_alembic_version",
        version_table_schema="public",
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
