"""add document folder path

Revision ID: d1e98bc2a7f4
Revises: 7cf46b564bc4
Create Date: 2026-10-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e98bc2a7f4"
down_revision: Union[str, Sequence[str], None] = "7cf46b564bc4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为文档增加轻量文件夹路径，并为现有样例资料补充分组。"""
    op.add_column("documents", sa.Column("folder_path", sa.String(length=255), nullable=True))
    op.create_index("ix_documents_folder_path", "documents", ["folder_path"], unique=False)
    op.execute(
        """
        UPDATE documents
        SET folder_path = CASE business_line
            WHEN 'auto_insurance' THEN '车险'
            WHEN 'health_insurance' THEN '健康险'
            WHEN 'travel_insurance' THEN '旅行险'
            WHEN 'property_insurance' THEN '家财险'
            WHEN 'life_insurance' THEN '人身险'
            WHEN 'policy_service' THEN '保单服务'
            WHEN 'claims_service' THEN '理赔服务'
            WHEN 'customer_service' THEN '客服运营'
            WHEN 'compliance' THEN '合规'
            ELSE '未分类'
        END
        WHERE folder_path IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_documents_folder_path", table_name="documents")
    op.drop_column("documents", "folder_path")
