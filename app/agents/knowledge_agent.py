import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from app.agents.knowledge_tools import KNOWLEDGE_TOOLS, execute_knowledge_tool
from app.core.config import settings
from app.services.llm_service import get_llm_client
from app.services.rag_service import RAGService
from app.services.llm_observability_service import extract_usage

@dataclass
class AgentRunResult:
    answer: str
    tool_calls: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class KnowledgeAgent:
    """基于 Tool Calling 的保险售后知识问答 Agent。"""

    SYSTEM_PROMPT = """
你是保知通的互联网保险售后知识问答 Agent。

规则：
1. 涉及保险产品、理赔、退保、续保、保单服务、投诉处理或业务规则时，
   必须先调用 search_knowledge 检索资料。
2. 只能依据工具返回的资料回答事实性问题；资料不足时明确说明，并建议人工确认。
3. 不承诺赔付金额、理赔结论或审批结果。
4. 回答时指出参考的文件名。
"""

    def __init__(self, rag_service: RAGService):
        self.rag_service = rag_service

    async def run(
        self,
        *,
        query: str,
        owner_id: int,
        history: Optional[list[dict[str, str]]] = None,
        business_line: Optional[str] = None,
        product: Optional[str] = None,
        as_of: Optional[datetime] = None,
        document_id: Optional[int] = None,
        folder_path: Optional[str] = None,
    ) -> AgentRunResult:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            *(history or []),
            {"role": "user", "content": query},
        ]

        llm_info = get_llm_client()
        tool_trace: list[dict[str, Any]] = []
        source_by_chunk: dict[tuple[int, int], dict[str, Any]] = {}
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        # 最多允许三轮：模型选工具 → 后端执行 → 模型继续思考。
        for _ in range(3):
            request_kwargs: dict[str, Any] = {
                "model": llm_info.model_name,
                "messages": messages,
                "tools": KNOWLEDGE_TOOLS,
                "tool_choice": "auto",
                "temperature": 0.1,
            }

            # DeepSeek 默认可能进入思考模式；这里先固定为非思考模式，
            # 便于使用 Chat Completions 的标准 Tool Calling 格式。
            if settings.LLM_PROVIDER == "deepseek":
                request_kwargs["extra_body"] = {
                    "thinking": {"type": "disabled"}
                }

            response = await llm_info.client.chat.completions.create(
                **request_kwargs
            )

            current_prompt, current_completion, current_total = extract_usage(
                response
            )
            prompt_tokens += current_prompt
            completion_tokens += current_completion
            total_tokens += current_total
            assistant_message = response.choices[0].message
            tool_calls = assistant_message.tool_calls or []

            # 模型没有继续调用工具，说明它已形成最终答案。
            if not tool_calls:
                return AgentRunResult(
                    answer=assistant_message.content
                    or "暂时无法生成回答，请稍后重试。",
                    tool_calls=tool_trace,
                    sources=list(source_by_chunk.values()),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )

            # 先把“模型发出的工具调用”加入对话历史。
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                        for tool_call in tool_calls
                    ],
                }
            )

            # 后端逐个执行模型选择的工具，再把结果回传给模型。
            for tool_call in tool_calls:
                try:
                    arguments = json.loads(tool_call.function.arguments)
                    if not isinstance(arguments, dict):
                        raise ValueError("工具参数必须是 JSON 对象。")
                except (json.JSONDecodeError, ValueError) as error:
                    tool_result = {"error": f"工具参数无效：{error}"}
                else:
                    tool_result = await execute_knowledge_tool(
                        tool_call.function.name,
                        arguments,
                        rag_service=self.rag_service,
                        owner_id=owner_id,
                        business_line=business_line,
                        product=product,
                        as_of=as_of,
                        document_id=document_id,
                        folder_path=folder_path,
                    )

                tool_trace.append(
                    {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    }
                )

                for source in tool_result.get("results", []):
                    key = (source["document_id"], source["chunk_index"])
                    source_by_chunk[key] = source

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(
                            tool_result,
                            ensure_ascii=False,
                        ),
                    }
                )

        return AgentRunResult(
            answer="已多次检索资料，但仍无法形成可靠回答，建议转人工确认。",
            tool_calls=tool_trace,
            sources=list(source_by_chunk.values()),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )