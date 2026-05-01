import uuid

import pytest

from luplo_cloud.glossary_ext.suggest_cli.save import save_decisions
from luplo_cloud.glossary_ext.suggest_cli.session import SuggestSession


@pytest.mark.asyncio
async def test_save_decisions_atomic_commit(
    oss_conn, seed_project, seed_actor, seed_group,
):
    sid = str(uuid.uuid4())
    await oss_conn.execute(
        "INSERT INTO glossary_suggestions"
        " (id, project_id, kind, candidate_surface, candidate_normalized,"
        "  target_group_id, similarity, extracted_by_model, reserved_by, reserved_at)"
        " VALUES (%s, %s, 'pair', %s, %s, %s, %s, %s, %s, now())",
        (sid, seed_project, "QPS 제한", "qps 제한",
         seed_group, 0.91, "qwen/qwen3.6-35b-a3b", seed_actor),
    )
    sess = SuggestSession([{
        "id": sid, "kind": "pair", "candidate_surface": "QPS 제한",
        "candidate_normalized": "qps 제한", "target_group_id": seed_group,
    }])
    sess.decisions[sid] = {"decision": "alias"}
    summary = await save_decisions(oss_conn, session=sess, actor_id=seed_actor)
    assert summary["alias"] == 1
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT consumed_decision FROM glossary_suggestions WHERE id = %s", (sid,)
        )
        row = await cur.fetchone()
    assert row[0] == "alias"
