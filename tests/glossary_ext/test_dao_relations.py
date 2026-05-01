import uuid

import pytest

from luplo_cloud.glossary_ext.dao_relations import (
    add_relation,
    list_relations_for_group,
)


@pytest.mark.asyncio
async def test_add_sibling_normalizes_pair_order(
    oss_conn, seed_project, seed_actor, seed_group
):
    # second group
    gid_b = f"grp-{uuid.uuid4().hex[:8]}"
    await oss_conn.execute(
        "INSERT INTO glossary_groups (id, project_id, scope, canonical, created_by)"
        " VALUES (%s, %s, 'project', %s, %s)",
        (gid_b, seed_project, "throttling", seed_actor),
    )
    rel_id = await add_relation(
        oss_conn,
        project_id=seed_project,
        group_x_id=seed_group,
        group_y_id=gid_b,
        relation="sibling",
        registered_by=seed_actor,
        reason="different but same dimension",
    )
    rels = await list_relations_for_group(oss_conn, group_id=seed_group)
    assert any(r["id"] == rel_id for r in rels)
    assert all(r["group_a_id"] < r["group_b_id"] for r in rels)


@pytest.mark.asyncio
async def test_add_relation_dedupes(
    oss_conn, seed_project, seed_actor, seed_group
):
    gid_b = f"grp-{uuid.uuid4().hex[:8]}"
    await oss_conn.execute(
        "INSERT INTO glossary_groups (id, project_id, scope, canonical, created_by)"
        " VALUES (%s, %s, 'project', %s, %s)",
        (gid_b, seed_project, "QPS 제한", seed_actor),
    )
    r1 = await add_relation(
        oss_conn, project_id=seed_project,
        group_x_id=seed_group, group_y_id=gid_b,
        relation="sibling", registered_by=seed_actor,
    )
    r2 = await add_relation(
        oss_conn, project_id=seed_project,
        group_x_id=gid_b, group_y_id=seed_group,  # swapped
        relation="sibling", registered_by=seed_actor,
    )
    assert r1 == r2
