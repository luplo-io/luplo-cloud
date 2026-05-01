import pytest

from luplo_cloud.glossary_ext.dao_history import list_history_for_group, record_history


@pytest.mark.asyncio
async def test_record_and_list_history(oss_conn, seed_project, seed_actor, seed_group):
    await record_history(
        oss_conn,
        group_id=seed_group,
        action="canonical_changed",
        old_value={"canonical": "rate limit"},
        new_value={"canonical": "QPS 제한"},
        changed_by=seed_actor,
        reason="domain prefers Korean term",
    )
    rows = await list_history_for_group(oss_conn, group_id=seed_group)
    assert len(rows) == 1
    assert rows[0]["action"] == "canonical_changed"
    assert rows[0]["new_value"]["canonical"] == "QPS 제한"
    assert rows[0]["reason"] == "domain prefers Korean term"
