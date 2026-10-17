from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class KnowledgeUpdate(Base):
    """保险业务知识更新。"""

    __tablename__ = "knowledge_updates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    title: Mapped[str] = mapped_column(
        String(255),
        index=True,
    )

    summary: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    content: Mapped[str] = mapped_column(Text)

    # product / claims / service / compliance
    category: Mapped[str] = mapped_column(
        String(50),
        default="service",
        index=True,
    )

    # normal / important / urgent
    priority: Mapped[str] = mapped_column(
        String(20),
        default="normal",
        index=True,
    )

    version: Mapped[str] = mapped_column(
        String(50),
        default="1.0",
    )

    # draft / published / archived
    status: Mapped[str] = mapped_column(
        String(20),
        default="draft",
        index=True,
    )

    effective_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    creator = relationship(
        "User",
        foreign_keys=[created_by_id],
    )

    reads = relationship(
        "KnowledgeUpdateRead",
        back_populates="knowledge_update",
        cascade="all, delete-orphan",
    )


class KnowledgeUpdateRead(Base):
    """客服对知识更新的阅读记录。"""

    __tablename__ = "knowledge_update_reads"

    __table_args__ = (
        UniqueConstraint(
            "knowledge_update_id",
            "user_id",
            name="uq_knowledge_update_read_user",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    knowledge_update_id: Mapped[int] = mapped_column(
        ForeignKey(
            "knowledge_updates.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    knowledge_update = relationship(
        "KnowledgeUpdate",
        back_populates="reads",
    )

    user = relationship("User")
