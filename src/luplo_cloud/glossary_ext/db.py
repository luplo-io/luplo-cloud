"""Async engine factory for the glossary extension.

The glossary extension targets the OSS luplo Postgres DB. Callers provide
a sync URL (`postgresql://...`); we coerce the driver to `asyncpg`. The
factory returns a fresh async engine per call — callers are responsible
for `dispose()` at process shutdown.
"""
from __future__ import annotations

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def async_engine_factory(url: str, *, echo: bool = False) -> AsyncEngine:
    u = make_url(url).set(query={})
    if u.drivername in ("postgresql", "postgres"):
        u = u.set(drivername="postgresql+asyncpg")
    return create_async_engine(u.render_as_string(hide_password=False), echo=echo)
