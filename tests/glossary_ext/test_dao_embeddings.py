import pytest

from luplo_cloud.glossary_ext.dao_embeddings import (
    list_embeddings_for_normalized,
    upsert_embedding,
)


@pytest.mark.asyncio
async def test_upsert_embedding_inserts(oss_conn, seed_project):
    eid = await upsert_embedding(
        oss_conn,
        project_id=seed_project,
        surface="QPS 제한",
        normalized="qps 제한",
        model_id="baai/bge-m3",
        vector=None,  # vector arg is nullable; workers populate it later
        linked_term_id=None,
    )
    assert isinstance(eid, str)
    rows = await list_embeddings_for_normalized(
        oss_conn, project_id=seed_project, normalized="qps 제한"
    )
    assert len(rows) == 1
    assert rows[0]["surface"] == "QPS 제한"


@pytest.mark.asyncio
async def test_upsert_embedding_idempotent(oss_conn, seed_project):
    await upsert_embedding(
        oss_conn, project_id=seed_project,
        surface="rate limit", normalized="rate limit",
        model_id="baai/bge-m3", vector=None, linked_term_id=None,
    )
    await upsert_embedding(
        oss_conn, project_id=seed_project,
        surface="rate limit", normalized="rate limit",
        model_id="baai/bge-m3", vector=None, linked_term_id=None,
    )
    rows = await list_embeddings_for_normalized(
        oss_conn, project_id=seed_project, normalized="rate limit"
    )
    assert len(rows) == 1
