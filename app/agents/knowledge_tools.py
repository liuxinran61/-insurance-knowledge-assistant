from datetime import datetime
from typing import Any, Optional

from app.services.rag_service import RAGService


KNOWLEDGE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": (
                "检索互联网保险售后知识库。当用户询问理赔、保单、"
                "续保、退保、投诉处理、服务流程或规则时，必须优先调用该工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "用于检索知识库的精炼问题。",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回资料片段数量，1 到 5 之间。",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    }
]


async def execute_knowledge_tool(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    rag_service: RAGService,
    owner_id: int,
    business_line: Optional[str] = None,
    product: Optional[str] = None,
    as_of: Optional[datetime] = None,
    document_id: Optional[int] = None,
    folder_path: Optional[str] = None,
) -> dict[str, Any]:
    """执行模型请求的知识库工具，并返回可安全提供给模型的资料。"""

    if tool_name != "search_knowledge":
        return {"error": f"不支持的工具：{tool_name}"}

    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        return {"error": "工具参数 query 必须是非空字符串。"}

    raw_top_k = arguments.get("top_k", 3)
    top_k = raw_top_k if isinstance(raw_top_k, int) and not isinstance(raw_top_k, bool) else 3
    top_k = min(max(top_k, 1), 5)

    chunks = await rag_service.retrieve_relevant_chunks(
        query=query.strip(),
        owner_id=owner_id,
        top_k=top_k,
        business_line=business_line,
        product=product,
        as_of=as_of,
        document_id=document_id,
        folder_path=folder_path,
    )

    return {
        "query": query.strip(),
        "result_count": len(chunks),
        "results": [
            {
                "document_id": chunk.document.id,
                "filename": chunk.document.filename,
                "chunk_index": chunk.chunk_index,
                "folder_path": chunk.document.folder_path,
                "product": chunk.document.product,
                "knowledge_version": chunk.document.knowledge_version,
                "effective_at": (
                    chunk.document.effective_at.isoformat()
                    if chunk.document.effective_at
                    else None
                ),
                "content": chunk.content[:1500],
            }
            for chunk in chunks
        ],
    }