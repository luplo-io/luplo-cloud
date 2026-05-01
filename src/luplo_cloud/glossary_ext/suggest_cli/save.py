"""Transaction-wrapped batch save for the suggest CLI.

The "no partial saves" UX promise is enforced HERE — apply_decisions is
allowed to mutate many rows, but if any single decision raises (FK
violation, missing target, invalid state), we roll back the whole
batch so the user's view of the world stays consistent. The caller
must NOT pre-commit anything in the same connection between leasing
and save_decisions.
"""
from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

from luplo_cloud.glossary_ext.dao_suggestions import apply_decisions
from luplo_cloud.glossary_ext.suggest_cli.session import SuggestSession


async def save_decisions(
    conn: AsyncConnection[Any],
    *,
    session: SuggestSession,
    actor_id: str,
) -> dict[str, int]:
    """Apply all decisions atomically. Commits on success, rolls back on any error.

    Catches `BaseException` (not `Exception`) so a `KeyboardInterrupt`
    raised inside `apply_decisions` still triggers the rollback. The CLI
    caller is responsible for the lease-release step after re-raise.
    """
    try:
        summary = await apply_decisions(
            conn,
            actor_id=actor_id,
            decisions=session.to_apply_payload(),
        )
    except BaseException:
        await conn.rollback()
        raise
    await conn.commit()
    return summary
