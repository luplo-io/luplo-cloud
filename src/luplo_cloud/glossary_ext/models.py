"""SQLAlchemy ORM models for glossary extension tables.

These models are READ-AND-WRITE for the extension; FK targets in OSS
(glossary_groups, glossary_terms, items, projects, actors) are described
as raw column references because OSS uses dataclass + raw SQL — no
metadata to import. Alembic migrations 0001/0002 are the source of
truth for schema; these models mirror them.

Note: actor FKs (reserved_by/registered_by/changed_by) are typed `Uuid`
because OSS `actors.id` is `uuid`, not `text`. Other ID columns
(projects, glossary_groups, items, glossary_terms) remain TEXT.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _new_id() -> str:
    return str(uuid.uuid4())


class GlossaryExtBase(DeclarativeBase):
    """Separate metadata from luplo_saas.databases.base.Base — different DB."""
    pass


class Job(GlossaryExtBase):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_new_id)
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fail_reason: Mapped[str | None] = mapped_column(Text)
    status_changed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    kv: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','done','failed')", name="jobs_status_check"
        ),
    )


class GlossaryTermEmbedding(GlossaryExtBase):
    __tablename__ = "glossary_term_embeddings"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_new_id)
    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("projects.id"), nullable=False
    )
    surface: Mapped[str] = mapped_column(Text, nullable=False)
    normalized: Mapped[str] = mapped_column(Text, nullable=False)
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    # vector column intentionally omitted from ORM — accessed via raw SQL
    # because pgvector's SQLAlchemy type may not be installed.
    linked_term_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("glossary_terms.id")
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", "normalized", "model_id",
            name="uq_glossary_embedding_unique",
        ),
    )


class GlossarySuggestion(GlossaryExtBase):
    __tablename__ = "glossary_suggestions"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_new_id)
    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("projects.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_surface: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    target_group_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("glossary_groups.id")
    )
    similarity: Mapped[float | None] = mapped_column()
    source_item_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("items.id")
    )
    context_snippet: Mapped[str | None] = mapped_column(Text)
    extracted_by_model: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    reserved_by: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("actors.id")
    )
    reserved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_decision: Mapped[str | None] = mapped_column(Text)


class GlossaryGroupRelation(GlossaryExtBase):
    __tablename__ = "glossary_group_relations"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_new_id)
    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("projects.id"), nullable=False
    )
    group_a_id: Mapped[str] = mapped_column(
        Text, ForeignKey("glossary_groups.id"), nullable=False
    )
    group_b_id: Mapped[str] = mapped_column(
        Text, ForeignKey("glossary_groups.id"), nullable=False
    )
    relation: Mapped[str] = mapped_column(Text, nullable=False)
    registered_by: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("actors.id")
    )
    registered_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("group_a_id < group_b_id", name="group_relation_pair_order"),
        UniqueConstraint(
            "group_a_id", "group_b_id", "relation",
            name="uq_group_relation_pair",
        ),
    )


class GlossaryHistory(GlossaryExtBase):
    __tablename__ = "glossary_history"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_new_id)
    group_id: Mapped[str] = mapped_column(
        Text, ForeignKey("glossary_groups.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    changed_by: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("actors.id")
    )
    changed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    reason: Mapped[str | None] = mapped_column(Text)
