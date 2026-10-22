from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    business_line: Optional[str] = None
    product: Optional[str] = None
    knowledge_version: Optional[str] = None
    effective_at: Optional[datetime] = None
    folder_path: Optional[str] = None
    status: str
    chunks_count: int
    processing_task_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentResponse):
    """文档详情，包含已解析的文本内容，用于知识库预览。"""

    content: str


class RAGQueryRequest(BaseModel):
    query: str
    top_k: int = Field(3, ge=1, le=10)
    session_id: Optional[str] = Field(None, description="会话 ID，用于多轮对话上下文记忆")
    business_line: Optional[str] = Field(
        None,
        max_length=50,
        description="限定检索的业务线，例如 auto_insurance",
    )
    product: Optional[str] = Field(
        None,
        max_length=100,
        description="限定检索的产品名称",
    )
    as_of: Optional[datetime] = Field(
        None,
        description="按该时间点筛选已生效资料；不传则使用当前时间",
    )
    document_id: Optional[int] = Field(
        None,
        gt=0,
        description="限定检索的单份文档 ID",
    )
    folder_path: Optional[str] = Field(
        None,
        max_length=255,
        description="限定检索的文件夹路径，例如 车险/理赔",
    )


class SourceReference(BaseModel):
    """RAG 回答所依据的结构化资料引用。"""

    document_id: int
    chunk_index: int
    filename: str
    business_line: Optional[str] = None
    product: Optional[str] = None
    knowledge_version: Optional[str] = None
    effective_at: Optional[datetime] = None
    folder_path: Optional[str] = None
    excerpt: str


class RAGQueryResponse(BaseModel):
    query: str
    answer: str
    source_chunks: List[str]
    sources: List[SourceReference] = Field(default_factory=list)
