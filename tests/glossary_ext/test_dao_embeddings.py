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


@pytest.mark.asyncio
async def test_upsert_embedding_with_vector_persists_values(oss_conn, seed_project):
    """Exercises _vec_literal end-to-end via pgvector text round-trip."""
    # Schema fixes vector dim at 1024 (BGE-M3); pad signature values out.
    signature = [0.1, 0.2, -0.3, 1.5]
    vec = signature + [0.0] * (1024 - len(signature))
    await upsert_embedding(
        oss_conn,
        project_id=seed_project,
        surface="threshold",
        normalized="threshold",
        model_id="test-tiny",
        vector=vec,
        linked_term_id=None,
    )
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT vector::text FROM glossary_term_embeddings"
            " WHERE project_id = %s AND normalized = %s AND model_id = %s",
            (seed_project, "threshold", "test-tiny"),
        )
        row = await cur.fetchone()
    assert row is not None
    # pgvector text format is "[v1,v2,...]"; whitespace and exact float
    # repr can vary, so just sanity-check the values are recoverable.
    text = row[0]
    assert text.startswith("[") and text.endswith("]")
    parsed = [float(x) for x in text[1:-1].split(",")]
    assert len(parsed) == 1024
    for got, want in zip(parsed, vec, strict=True):
        assert abs(got - want) < 1e-6


@pytest.mark.asyncio
async def test_upsert_embedding_preserves_vector_on_null_reupsert(oss_conn, seed_project):
    """COALESCE preserves prior vector when new upsert passes None."""
    signature = [0.5, 0.6, 0.7]
    initial_vec = signature + [0.0] * (1024 - len(signature))
    await upsert_embedding(
        oss_conn,
        project_id=seed_project,
        surface="cache",
        normalized="cache",
        model_id="test-tiny",
        vector=initial_vec,
        linked_term_id=None,
    )
    await upsert_embedding(
        oss_conn,
        project_id=seed_project,
        surface="cache (updated)",
        normalized="cache",
        model_id="test-tiny",
        vector=None,
        linked_term_id=None,
    )
    async with oss_conn.cursor() as cur:
        await cur.execute(
            "SELECT surface, vector::text FROM glossary_term_embeddings"
            " WHERE project_id = %s AND normalized = %s AND model_id = %s",
            (seed_project, "cache", "test-tiny"),
        )
        row = await cur.fetchone()
    assert row is not None
    assert row[0] == "cache (updated)"  # surface overwritten
    assert row[1] is not None
    parsed = [float(x) for x in row[1][1:-1].split(",")]
    for got, want in zip(parsed, initial_vec, strict=True):
        assert abs(got - want) < 1e-6


@pytest.mark.asyncio
async def test_list_embeddings_for_normalized_returns_empty_when_missing(oss_conn, seed_project):
    rows = await list_embeddings_for_normalized(
        oss_conn, project_id=seed_project, normalized="never-inserted"
    )
    assert rows == []
