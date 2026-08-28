from datetime import date, datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AppUser(Base):
    __tablename__ = "app_user"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dingtalk_user_id: Mapped[Optional[str]] = mapped_column(Text, unique=True)
    feishu_open_id: Mapped[Optional[str]] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    is_global_admin: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Space(Base):
    __tablename__ = "space"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    security_level: Mapped[str] = mapped_column(Text, default="exec")
    confirmer_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    match_rules: Mapped[list] = mapped_column(JSONB, default=list)
    report_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SpaceMember(Base):
    __tablename__ = "space_member"
    space_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("space.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"), primary_key=True)
    role: Mapped[str] = mapped_column(Text, default="admin")


class Meeting(Base):
    __tablename__ = "meeting"
    __table_args__ = (UniqueConstraint("source", "source_ref"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    space_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("space.id"))
    title: Mapped[str] = mapped_column(Text)
    held_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(Text)
    source_ref: Mapped[dict] = mapped_column(JSONB, default=dict)
    participants: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(Text, default="ingested")
    extraction_version: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    segments: Mapped[list["TranscriptSegment"]] = relationship(back_populates="meeting", cascade="all, delete-orphan")


class TranscriptSegment(Base):
    __tablename__ = "transcript_segment"
    __table_args__ = (UniqueConstraint("meeting_id", "seq"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("meeting.id"))
    seq: Mapped[int] = mapped_column(Integer)
    speaker_name: Mapped[Optional[str]] = mapped_column(Text)
    speaker_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    start_ms: Mapped[Optional[int]] = mapped_column(BigInteger)
    end_ms: Mapped[Optional[int]] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(Text)
    search_vector: Mapped[Any] = mapped_column(TSVECTOR, nullable=True)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(1024))
    meeting: Mapped["Meeting"] = relationship(back_populates="segments")


class PlatformArtifact(Base):
    __tablename__ = "platform_artifact"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("meeting.id"))
    kind: Mapped[str] = mapped_column(Text)
    content: Mapped[Optional[str]] = mapped_column(Text)
    raw: Mapped[Optional[dict]] = mapped_column(JSONB)


class Topic(Base):
    __tablename__ = "topic"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    space_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("space.id"))
    name: Mapped[str] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(1024))
    merged_into: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("topic.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Entity(Base):
    __tablename__ = "entity"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("meeting.id"))
    space_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("space.id"))
    topic_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("topic.id"))
    type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB)
    anchor_segment_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger))
    status: Mapped[str] = mapped_column(Text, default="ai_extracted")
    auto_committed: Mapped[bool] = mapped_column(Boolean, default=False)
    extraction_version: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(3, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConfirmationTask(Base):
    __tablename__ = "confirmation_task"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("meeting.id"), unique=True)
    confirmer_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, default="pending")


class EntityRevision(Base):
    __tablename__ = "entity_revision"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("entity.id"))
    editor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    action: Mapped[str] = mapped_column(Text)
    before: Mapped[Optional[dict]] = mapped_column(JSONB)
    after: Mapped[Optional[dict]] = mapped_column(JSONB)
    edited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Report(Base):
    __tablename__ = "report"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    space_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("space.id"))
    period_label: Mapped[str] = mapped_column(Text)
    meeting_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger))
    content_md: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="draft")
    finalized_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    action: Mapped[str] = mapped_column(Text)
    target_type: Mapped[Optional[str]] = mapped_column(Text)
    target_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    detail: Mapped[Optional[dict]] = mapped_column(JSONB)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LlmUsage(Base):
    __tablename__ = "llm_usage"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    task: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    cost_estimate: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    meeting_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatSession(Base):
    __tablename__ = "chat_session"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    space_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("space.id"))
    topic_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("topic.id"))
    date_from: Mapped[Optional[date]] = mapped_column(Date)
    date_to: Mapped[Optional[date]] = mapped_column(Date)
    title: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatMessage(Base):
    __tablename__ = "chat_message"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chat_session.id"))
    role: Mapped[str] = mapped_column(Text)
    content_md: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSONB, default=list)
    tool_trace: Mapped[Optional[list]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EntityMention(Base):
    __tablename__ = "entity_mention"
    __table_args__ = (UniqueConstraint("entity_id", "segment_id"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("entity.id"))
    meeting_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("meeting.id"))
    segment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("transcript_segment.id"))
    mention_kind: Mapped[str] = mapped_column(Text)
    similarity: Mapped[Optional[float]] = mapped_column(Numeric(3, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SyncRun(Base):
    __tablename__ = "sync_run"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    space_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("space.id"))
    channel: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
