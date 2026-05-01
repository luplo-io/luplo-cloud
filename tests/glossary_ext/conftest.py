"""Test fixtures for the glossary extension.

Each test runs against the live OSS luplo test DB (assumed to be migrated
to head with `lp migrate` and the glossary-ext partition migrated with
`alembic -c alembic_luplo_ext.ini upgrade head`). Tests wrap each call in
a transaction that is rolled back at teardown — no data pollution between
tests.

DB URL precedence: LUPLO_EXT_TEST_DB_URL → LUPLO_TEST_DB_URL → default.
"""
from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import psycopg
import pytest_asyncio
from sqlalchemy.engine.url import make_url


def _resolve_test_db_url() -> str:
    return (
        os.environ.get("LUPLO_EXT_TEST_DB_URL")
        or os.environ.get("LUPLO_TEST_DB_URL")
        or "postgresql://postgres:localdb@localhost:5433/luplo_test"
    )


def _to_sync_url(url: str) -> str:
    u = make_url(url).set(query={})
    if u.drivername.startswith("postgresql+"):
        u = u.set(drivername="postgresql")
    return u.render_as_string(hide_password=False)


@pytest_asyncio.fixture
async def oss_conn() -> AsyncGenerator[psycopg.AsyncConnection[Any], None]:
    """Async psycopg connection wrapped in a rollback transaction."""
    url = _to_sync_url(_resolve_test_db_url())
    conn = await psycopg.AsyncConnection.connect(url)
    try:
        yield conn
    finally:
        await conn.rollback()
        await conn.close()


@pytest_asyncio.fixture
async def seed_project(oss_conn: psycopg.AsyncConnection[Any]) -> str:
    pid = f"proj-{uuid.uuid4().hex[:8]}"
    await oss_conn.execute(
        "INSERT INTO projects (id, name) VALUES (%s, %s)",
        (pid, f"Test Project {pid}"),
    )
    return pid


@pytest_asyncio.fixture
async def seed_actor(oss_conn: psycopg.AsyncConnection[Any]) -> str:
    aid = f"actor-{uuid.uuid4().hex[:8]}"
    await oss_conn.execute(
        "INSERT INTO actors (id, name) VALUES (%s, %s)",
        (aid, f"Test Actor {aid}"),
    )
    return aid


@pytest_asyncio.fixture
async def seed_group(
    oss_conn: psycopg.AsyncConnection[Any],
    seed_project: str,
    seed_actor: str,
) -> str:
    gid = f"grp-{uuid.uuid4().hex[:8]}"
    await oss_conn.execute(
        "INSERT INTO glossary_groups (id, project_id, scope, canonical, created_by)"
        " VALUES (%s, %s, 'project', %s, %s)",
        (gid, seed_project, "rate limit", seed_actor),
    )
    await oss_conn.execute(
        "INSERT INTO glossary_terms (id, group_id, surface, normalized, status)"
        " VALUES (%s, %s, %s, %s, 'canonical')",
        (f"term-{uuid.uuid4().hex[:8]}", gid, "rate limit", "rate limit"),
    )
    return gid
