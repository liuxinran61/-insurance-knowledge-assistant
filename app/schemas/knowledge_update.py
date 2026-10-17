from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Literal 表示字段只允许使用列出的值。
KnowledgeCategory = Literal[
    "product",
    "claims",
    "service",
    "compliance",
]

KnowledgePriority = Literal[
    "normal",
    "important",
    "urgent",
]

KnowledgeStatus = Literal[
    "draft",
    "published",
    "archived",
]


class KnowledgeUpdateBase(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="知识更新标题",
    )

    summary: Optional[str] = Field(
        None,
        max_length=500,
        description="知识更新摘要",
    )

    content: str = Field(
        ...,
        min_length=1,
        description="知识更新正文",
    )

    category: KnowledgeCategory = Field(
        "service",
        description="分类：产品、理赔、服务或合规",
    )

    priority: KnowledgePriority = Field(
        "normal",
        description="重要程度：普通、重要或紧急",
    )

    version: str = Field(
        "1.0",
        min_length=1,
        max_length=50,
        description="知识版本号",
    )

    effective_at: Optional[datetime] = Field(
        None,
        description="业务规则生效时间",
    )


class KnowledgeUpdateCreate(KnowledgeUpdateBase):
    """创建知识更新时接收的数据。"""

    pass


class KnowledgeUpdateUpdate(BaseModel):
    """编辑草稿时接收的数据，所有字段均可选。"""

    title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
    )
    summary: Optional[str] = Field(
        None,
        max_length=500,
    )
    content: Optional[str] = Field(
        None,
        min_length=1,
    )
    category: Optional[KnowledgeCategory] = None
    priority: Optional[KnowledgePriority] = None
    version: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
    )
    effective_at: Optional[datetime] = None


class KnowledgeUpdateOut(KnowledgeUpdateBase):
    """返回给前端的知识更新及当前用户阅读状态。"""

    id: int
    status: KnowledgeStatus
    created_by_id: int
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    is_read: bool = False
    read_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class KnowledgeUpdateReadOut(BaseModel):
    """返回给前端的知识阅读记录。"""

    id: int
    knowledge_update_id: int
    user_id: int
    read_at: datetime

    model_config = ConfigDict(from_attributes=True)
