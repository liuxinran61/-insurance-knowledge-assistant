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
    },
    {
        "type": "function",
        "function": {
            "name": "assess_service_risk",
            "description": (
                "识别保险售后对话中的投诉、拒赔争议、监管风险、"
                "隐私风险或不当承诺风险。仅当问题包含上述高风险信号时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "需要进行风险识别的客户原始表述。",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]


def assess_service_risk(query: str) -> dict[str, Any]:
    """基于明确规则识别客服场景风险，不依赖模型自由判断。"""

    normalized_query = query.strip().lower()
    matched_signals: list[str] = []

    signal_rules = {
        "投诉升级": ("投诉", "消协", "监管", "媒体曝光"),
        "理赔争议": (
            "拒赔",
            "不赔",
            "赔少了",
            "理赔争议",
            "赔多少",
            "赔偿多少",
            "最终能赔",
        ),
        "隐私风险": ("身份证", "银行卡", "隐私", "个人信息"),
        "不当承诺": (
            "保证赔",
            "一定赔",
            "马上到账",
            "全额赔",
            "承诺",
            "保费不涨",
            "不涨价",
        ),
    }

    for label, keywords in signal_rules.items():
        if any(keyword in normalized_query for keyword in keywords):
            matched_signals.append(label)

    if not matched_signals:
        return {
            "risk_level": "low",
            "matched_signals": [],
            "requires_human_handoff": False,
            "agent_guidance": [
                "当前未发现高风险信号，可继续按知识库资料进行常规答复。",
            ],
        }

    high_risk_signals = {"投诉升级", "理赔争议", "隐私风险"}
    is_high_risk = any(
        signal in high_risk_signals
        for signal in matched_signals
    )

    guidance = [
        "记录客户诉求、已知事实和已沟通内容。",
        "不得承诺赔付结论、处理时效或补偿金额。",
    ]

    if "隐私风险" in matched_signals:
        guidance.append("不要在对话中索取或重复展示完整身份证号、银行卡号等敏感信息。")

    if is_high_risk:
        guidance.append("建议按投诉或争议流程转人工进一步处理。")

    return {
        "risk_level": "high" if is_high_risk else "medium",
        "matched_signals": matched_signals,
        "requires_human_handoff": is_high_risk,
        "agent_guidance": guidance,
    }


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

    if tool_name == "assess_service_risk":
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            return {"error": "工具参数 query 必须是非空字符串。"}
        return assess_service_risk(query)

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
