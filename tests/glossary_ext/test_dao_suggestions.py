import uuid

import pytest

from luplo_cloud.glossary_ext.dao_suggestions import (
    apply_decisions,
    lease_suggestions,
    release_lease,
)


async def _seed_suggestion(
    conn, *, project_id, kind="pair", target_group_id=None, surface="QPS 제한",
):
    sid = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO glossary_suggestions"
        " (id, project_id, kind, candidate_surface, candidate_normalized,"
        "  target_group_id, similarity, extracted_by_model)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (sid, project_id, kind, surface, surface.lower(), target_group_id,
         0.91 if kind == "pair" else None, "qwen/qwen3.6-35b-a3b"),
    )
    return sid


async def _seed_other_actor(conn) -> str:
    aid = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO actors (id, name, email) VALUES (%s, %s, %s)",
        (aid, f"Other Actor {aid[:8]}", f"{aid}@test.local"),
    )
    return aid


@pytest.mark.asyncio
async def test_lease_and_release(oss_conn, seed_project, seed_actor, seed_group):
    sid = await _seed_suggestion(
        oss_conn, project_id=seed_project, target_group_id=seed_group,
    )
    leased = await lease_suggestions(
        oss_conn,
        project_id=seed_project,
        leased_by=seed_actor,
        limit=10,
        stale_after_minutes=30,
    )
    assert len(leased) == 1
    assert leased[0]["id"] == sid

    # second lease attempt by another actor returns nothing
    other_actor = await _seed_other_actor(oss_conn)
    leased2 = await lease_suggestions(
        oss_conn, project_id=seed_project, leased_by=other_actor,
        limit=10, stale_after_minutes=30,
    )
    assert leased2 == []

    await release_lease(oss_conn, leased_by=seed_actor)
    leased3 = await lease_suggestions(
        oss_conn, project_id=seed_project, leased_by=other_actor,
        limit=10, stale_after_minutes=30,
    )
    assert len(leased3) == 1


@pytest.mark.asyncio
async def test_stale_lease_can_be_reclaimed(oss_conn, seed_project, seed_actor, seed_group):
    sid = await _seed_suggestion(
        oss_conn, project_id=seed_project, target_group_id=seed_group,
    )
    # Manually stamp a stale lease
    await oss_conn.execute(
        "UPDATE glossary_suggestions"
        " SET reserved_by = %s, reserved_at = now() - interval '45 minutes'"
        " WHERE id = %s",
        (seed_actor, sid),
    )
    other = await _seed_other_actor(oss_conn)
    leased = await lease_suggestions(
        oss_conn, project_id=seed_project, leased_by=other,
        limit=10, stale_after_minutes=30,
    )
    assert len(leased) == 1
    assert leased[0]["id"] == sid


@pytest.mark.asyncio
async def test_apply_decisions_alias_writes_term_and_marks_consumed(
    oss_conn, seed_project, seed_actor, seed_group,
):
    sid = await _seed_suggestion(
        oss_conn, project_id=seed_project, target_group_id=seed_group,
    )
    await lease_suggestions(
        oss_conn, project_id=seed_project, leased_by=seed_actor,
        limit=10, stale_after_minutes=30,
    )
    summary = await apply_decisions(
        oss_conn,
        actor_id=seed_actor,
        decisions=[{"suggestion_id": sid, "decision": "alias"}],
    )
    assert summary["alias"] == 1
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT consumed_at, consumed_decision FROM glossary_suggestions WHERE id = %s",
            (sid,),
        )
        row = await cur.fetchone()
    assert row[0] is not None
    assert row[1] == "alias"
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM glossary_terms"
            " WHERE group_id = %s AND surface = 'QPS 제한' AND status = 'alias'",
            (seed_group,),
        )
        assert (await cur.fetchone())[0] == 1


@pytest.mark.asyncio
async def test_apply_decisions_skip_does_not_consume(
    oss_conn, seed_project, seed_actor, seed_group,
):
    sid = await _seed_suggestion(
        oss_conn, project_id=seed_project, target_group_id=seed_group,
    )
    await lease_suggestions(
        oss_conn, project_id=seed_project, leased_by=seed_actor,
        limit=10, stale_after_minutes=30,
    )
    await apply_decisions(
        oss_conn, actor_id=seed_actor,
        decisions=[{"suggestion_id": sid, "decision": "skip"}],
    )
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT consumed_at, reserved_by FROM glossary_suggestions WHERE id = %s",
            (sid,),
        )
        row = await cur.fetchone()
    assert row[0] is None  # not consumed
    assert row[1] is None  # lease released


@pytest.mark.asyncio
async def test_apply_decisions_canonical_replace_demotes_and_replaces(
    oss_conn, seed_project, seed_actor, seed_group,
):
    sid = await _seed_suggestion(
        oss_conn, project_id=seed_project, target_group_id=seed_group,
        surface="QPS 제한",
    )
    await lease_suggestions(
        oss_conn, project_id=seed_project, leased_by=seed_actor,
        limit=10, stale_after_minutes=30,
    )
    summary = await apply_decisions(
        oss_conn, actor_id=seed_actor,
        decisions=[{
            "suggestion_id": sid,
            "decision": "canonical_replace",
            "reason": "domain prefers Korean term",
        }],
    )
    assert summary["canonical_replace"] == 1
    # Old canonical now alias
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM glossary_terms"
            " WHERE group_id = %s AND surface = 'rate limit' AND status = 'alias'",
            (seed_group,),
        )
        assert (await cur.fetchone())[0] == 1
        # New canonical present
        await cur.execute(
            "SELECT count(*) FROM glossary_terms"
            " WHERE group_id = %s AND surface = 'QPS 제한' AND status = 'canonical'",
            (seed_group,),
        )
        assert (await cur.fetchone())[0] == 1
        # Group canonical updated
        await cur.execute(
            "SELECT canonical FROM glossary_groups WHERE id = %s",
            (seed_group,),
        )
        assert (await cur.fetchone())[0] == "QPS 제한"
        # canonical_changed history captures old value (I-3 fix)
        await cur.execute(
            "SELECT old_value, new_value FROM glossary_history"
            " WHERE group_id = %s AND action = 'canonical_changed'",
            (seed_group,),
        )
        hist = await cur.fetchone()
    assert hist[0] == {"canonical": "rate limit"}
    assert hist[1] == {"canonical": "QPS 제한"}


@pytest.mark.asyncio
async def test_apply_decisions_canonical_replace_requires_reason(
    oss_conn, seed_project, seed_actor, seed_group,
):
    sid = await _seed_suggestion(
        oss_conn, project_id=seed_project, target_group_id=seed_group,
    )
    await lease_suggestions(
        oss_conn, project_id=seed_project, leased_by=seed_actor,
        limit=10, stale_after_minutes=30,
    )
    with pytest.raises(ValueError, match="reason"):
        await apply_decisions(
            oss_conn, actor_id=seed_actor,
            decisions=[{"suggestion_id": sid, "decision": "canonical_replace"}],
        )


@pytest.mark.asyncio
async def test_apply_decisions_alias_requires_target_group_id(
    oss_conn, seed_project, seed_actor,
):
    # Seed a suggestion WITHOUT target_group_id (kind='term')
    sid = await _seed_suggestion(
        oss_conn, project_id=seed_project, kind="term",
        target_group_id=None, surface="orphan",
    )
    await lease_suggestions(
        oss_conn, project_id=seed_project, leased_by=seed_actor,
        limit=10, stale_after_minutes=30,
    )
    with pytest.raises(ValueError, match="target_group_id"):
        await apply_decisions(
            oss_conn, actor_id=seed_actor,
            decisions=[{"suggestion_id": sid, "decision": "alias"}],
        )


@pytest.mark.asyncio
async def test_apply_decisions_sibling_creates_group_term_and_relation(
    oss_conn, seed_project, seed_actor, seed_group,
):
    sid = await _seed_suggestion(
        oss_conn, project_id=seed_project, target_group_id=seed_group,
        surface="throttling",
    )
    await lease_suggestions(
        oss_conn, project_id=seed_project, leased_by=seed_actor,
        limit=10, stale_after_minutes=30,
    )
    summary = await apply_decisions(
        oss_conn, actor_id=seed_actor,
        decisions=[{"suggestion_id": sid, "decision": "sibling"}],
    )
    assert summary["sibling"] == 1
    async with oss_conn.cursor() as cur:
        # New group exists
        await cur.execute(
            "SELECT id FROM glossary_groups"
            " WHERE project_id = %s AND canonical = 'throttling'",
            (seed_project,),
        )
        new_group = await cur.fetchone()
        assert new_group is not None
        # Sibling relation row exists between seed_group and new_group
        await cur.execute(
            "SELECT count(*) FROM glossary_group_relations"
            " WHERE relation = 'sibling'"
            "   AND ((group_a_id = %s AND group_b_id = %s)"
            "     OR (group_a_id = %s AND group_b_id = %s))",
            (seed_group, new_group[0], new_group[0], seed_group),
        )
        assert (await cur.fetchone())[0] == 1


@pytest.mark.asyncio
async def test_apply_decisions_create_uses_new_canonical_override(
    oss_conn, seed_project, seed_actor,
):
    sid = await _seed_suggestion(
        oss_conn, project_id=seed_project, kind="term",
        target_group_id=None, surface="raw_surface",
    )
    await lease_suggestions(
        oss_conn, project_id=seed_project, leased_by=seed_actor,
        limit=10, stale_after_minutes=30,
    )
    summary = await apply_decisions(
        oss_conn, actor_id=seed_actor,
        decisions=[{
            "suggestion_id": sid, "decision": "create",
            "new_canonical": "Polished Surface",
        }],
    )
    assert summary["create"] == 1
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT canonical FROM glossary_groups"
            " WHERE project_id = %s AND canonical = 'Polished Surface'",
            (seed_project,),
        )
        assert (await cur.fetchone())[0] == "Polished Surface"


@pytest.mark.asyncio
async def test_apply_decisions_reject_writes_rejection_row(
    oss_conn, seed_project, seed_actor, seed_group,
):
    sid = await _seed_suggestion(
        oss_conn, project_id=seed_project, target_group_id=seed_group,
        surface="not-a-thing",
    )
    await lease_suggestions(
        oss_conn, project_id=seed_project, leased_by=seed_actor,
        limit=10, stale_after_minutes=30,
    )
    summary = await apply_decisions(
        oss_conn, actor_id=seed_actor,
        decisions=[{"suggestion_id": sid, "decision": "reject", "reason": "irrelevant"}],
    )
    assert summary["reject"] == 1
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM glossary_rejections"
            " WHERE group_id = %s AND rejected_term = 'not-a-thing'",
            (seed_group,),
        )
        assert (await cur.fetchone())[0] == 1
        # Suggestion consumed
        await cur.execute(
            "SELECT consumed_decision FROM glossary_suggestions WHERE id = %s",
            (sid,),
        )
        assert (await cur.fetchone())[0] == "reject"
