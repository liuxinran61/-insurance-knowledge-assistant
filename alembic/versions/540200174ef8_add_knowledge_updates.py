"""add knowledge updates

Revision ID: 540200174ef8
Revises: b35f62ae79bf
Create Date: 2026-10-16 11:56:56.970788

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '540200174ef8'
down_revision: Union[str, Sequence[str], None] = 'b35f62ae79bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建知识更新及用户已读记录表。"""

    op.create_table(
        "knowledge_updates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "effective_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_knowledge_updates_id",
        "knowledge_updates",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_updates_title",
        "knowledge_updates",
        ["title"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_updates_category",
        "knowledge_updates",
        ["category"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_updates_priority",
        "knowledge_updates",
        ["priority"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_updates_status",
        "knowledge_updates",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_updates_created_by_id",
        "knowledge_updates",
        ["created_by_id"],
        unique=False,
    )

    op.create_table(
        "knowledge_update_reads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "knowledge_update_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_update_id"],
            ["knowledge_updates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "knowledge_update_id",
            "user_id",
            name="uq_knowledge_update_read_user",
        ),
    )

    op.create_index(
        "ix_knowledge_update_reads_id",
        "knowledge_update_reads",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_update_reads_knowledge_update_id",
        "knowledge_update_reads",
        ["knowledge_update_id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_update_reads_user_id",
        "knowledge_update_reads",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """删除知识更新及用户已读记录表。"""

    op.drop_index(
        "ix_knowledge_update_reads_user_id",
        table_name="knowledge_update_reads",
    )
    op.drop_index(
        "ix_knowledge_update_reads_knowledge_update_id",
        table_name="knowledge_update_reads",
    )
    op.drop_index(
        "ix_knowledge_update_reads_id",
        table_name="knowledge_update_reads",
    )
    op.drop_table("knowledge_update_reads")

    op.drop_index(
        "ix_knowledge_updates_created_by_id",
        table_name="knowledge_updates",
    )
    op.drop_index(
        "ix_knowledge_updates_status",
        table_name="knowledge_updates",
    )
    op.drop_index(
        "ix_knowledge_updates_priority",
        table_name="knowledge_updates",
    )
    op.drop_index(
        "ix_knowledge_updates_category",
        table_name="knowledge_updates",
    )
    op.drop_index(
        "ix_knowledge_updates_title",
        table_name="knowledge_updates",
    )
    op.drop_index(
        "ix_knowledge_updates_id",
        table_name="knowledge_updates",
    )
    op.drop_table("knowledge_updates")