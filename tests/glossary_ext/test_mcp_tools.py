import uuid

import pytest

from luplo_cloud.glossary_ext.mcp_tools import (
    glossary_add_group,
    glossary_link,
    glossary_link_sibling,
    preview_glossary_link,
)


@pytest.mark.asyncio
async def test_glossary_add_group_creates_group_and_canonical_term(
    oss_conn, seed_project, seed_actor,
):
    res = await glossary_add_group(
        oss_conn,
        project_id=seed_project,
        canonical="payment retry",
        definition="re-issue a failed payment",
        actor_id=seed_actor,
    )
    assert res["created"] is True
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT 1 FROM glossary_groups WHERE id = %s", (res["group_id"],)
        )
        assert await cur.fetchone() is not None
        await cur.execute(
            "SELECT 1 FROM glossary_terms WHERE group_id = %s AND status = 'canonical'",
            (res["group_id"],),
        )
        assert await cur.fetchone() is not None


@pytest.mark.asyncio
async def test_glossary_link_warns_on_prior_rejection(
    oss_conn, seed_project, seed_actor, seed_group,
):
    # Pre-reject "throttling" against the seed_group
    await oss_conn.execute(
        "INSERT INTO glossary_rejections (group_id, rejected_term, rejected_by, reason)"
        " VALUES (%s, %s, %s, %s)",
        (seed_group, "throttling", seed_actor, "different concept"),
    )
    preview = await preview_glossary_link(
        oss_conn,
        canonical_or_group_id=seed_group,
        alias_surface="throttling",
    )
    assert preview["previously_rejected"] is True
    assert preview["rejection_reason"] == "different concept"


@pytest.mark.asyncio
async def test_glossary_link_adds_alias(
    oss_conn, seed_project, seed_actor, seed_group,
):
    res = await glossary_link(
        oss_conn,
        canonical_or_group_id=seed_group,
        alias_surface="throttling",
        actor_id=seed_actor,
    )
    assert res["added"] is True
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM glossary_terms"
            " WHERE group_id = %s AND surface = 'throttling' AND status = 'alias'",
            (seed_group,),
        )
        assert (await cur.fetchone())[0] == 1


@pytest.mark.asyncio
async def test_glossary_link_sibling_creates_relation(
    oss_conn, seed_project, seed_actor, seed_group,
):
    other_id = f"grp-{uuid.uuid4().hex[:8]}"
    await oss_conn.execute(
        "INSERT INTO glossary_groups (id, project_id, scope, canonical, created_by)"
        " VALUES (%s, %s, 'project', %s, %s)",
        (other_id, seed_project, "throttling", seed_actor),
    )
    res = await glossary_link_sibling(
        oss_conn,
        project_id=seed_project,
        group_x_id=seed_group,
        group_y_id=other_id,
        actor_id=seed_actor,
        reason="adjacent concepts",
    )
    assert res["added"] is True
