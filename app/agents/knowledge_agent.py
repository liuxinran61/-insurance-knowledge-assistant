import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Optional

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


@dataclass
class ParsedToolFunction:
    """将非标准协议文本适配为 OpenAI Tool Calling 的最小结构。"""

    name: str
    arguments: str


@dataclass
class ParsedToolCall:
    """兼容 DeepSeek 偶发返回的 DSML 文本工具调用。"""

    id: str
    function: ParsedToolFunction


class KnowledgeAgent:
    """基于 Tool Calling 的保险售后知识问答 Agent。"""

    SYSTEM_PROMPT = """
你是保知通的互联网保险售后知识问答 Agent。

规则：
1. 涉及保险产品、理赔、退保、续保、保单服务、投诉处理或业务规则时，
   必须先调用 search_knowledge 检索资料。
2. 当问题涉及投诉、拒赔争议、监管、隐私或赔付承诺时，必须调用
   assess_service_risk；如果结果要求转人工，不得淡化该提示。
3. 只能依据工具返回的资料回答事实性问题；资料不足时明确说明，并建议人工确认。
4. 不承诺赔付金额、理赔结论或审批结果。
5. 回答时指出参考的文件名。
6. 必须通过原生 function calling 调用工具；严禁把 DSML、XML、函数调用标签或
   工具参数直接写进面向客服的回答。
"""
    NO_EVIDENCE_ANSWER = (
        "当前知识库未检索到可确认的规则或资料，"
        "无法据此给出具体结论。请核对对应保单条款、产品版本，"
        "并转交人工专员进一步确认。"
    )
    INCOMPLETE_EVIDENCE_ANSWER = (
        "已检索到部分相关资料，但无法确认完整的规则细节。"
        "请查阅对应产品版本的正式条款或转交人工专员进一步确认。"
    )
    FINAL_ANSWER_PROMPT = (
        "现在工具调用阶段已经结束。请仅根据已有工具结果，生成面向客服的最终答复。"
        "不得再次调用工具，不得输出 DSML、XML、函数名、函数参数或任何工具调用协议。"
    )
    _DSML_INVOKE_PATTERN = re.compile(
        r'<\|\|DSML\|\|\s+invoke\b[^>]*\bname="(?P<name>[^"]+)"[^>]*>'
        r'(?P<body>.*?)</\|\|DSML\|\|\s+invoke>',
        re.DOTALL,
    )
    _DSML_PARAMETER_PATTERN = re.compile(
        r'<\|\|DSML\|\|\s+parameter\b[^>]*\bname="(?P<name>[^"]+)"'
        r'(?P<attributes>[^>]*)>(?P<value>.*?)</\|\|DSML\|\|\s+parameter>',
        re.DOTALL,
    )

    def __init__(self, rag_service: RAGService):
        self.rag_service = rag_service

    @staticmethod
    def _tool_status(tool_name: str) -> str:
        """将内部工具名转换为可安全展示给客服的进度文案。"""
        return {
            "search_knowledge": "正在检索知识库资料…",
            "assess_service_risk": "正在评估服务风险…",
        }.get(tool_name, "正在调用业务工具…")

    @staticmethod
    def _normalise_dsml(content: str) -> str:
        """统一 DeepSeek DSML 标记中的全角竖线与转义闭合标签。"""

        return content.replace("｜", "|").replace("\\", "")

    @classmethod
    def _extract_dsml_tool_calls(
        cls,
        content: Optional[str],
        round_index: int,
    ) -> list[ParsedToolCall]:
        """解析 DeepSeek 的 DSML 文本工具调用，解析失败时安全地返回空列表。"""

        if not content or "DSML" not in content or "invoke" not in content:
            return []

        normalised = cls._normalise_dsml(content)
        calls: list[ParsedToolCall] = []
        supported_tools = {tool["function"]["name"] for tool in KNOWLEDGE_TOOLS}

        for call_index, match in enumerate(
            cls._DSML_INVOKE_PATTERN.finditer(normalised),
            start=1,
        ):
            tool_name = match.group("name")
            if tool_name not in supported_tools:
                continue

            arguments: dict[str, Any] = {}
            for parameter in cls._DSML_PARAMETER_PATTERN.finditer(match.group("body")):
                name = parameter.group("name")
                value = parameter.group("value").strip()
                attributes = parameter.group("attributes")

                if 'string="true"' in attributes:
                    arguments[name] = value
                elif re.fullmatch(r"-?\d+", value):
                    arguments[name] = int(value)
                elif value.lower() in {"true", "false"}:
                    arguments[name] = value.lower() == "true"
                else:
                    arguments[name] = value

            calls.append(
                ParsedToolCall(
                    id=f"dsml_{round_index}_{call_index}",
                    function=ParsedToolFunction(
                        name=tool_name,
                        arguments=json.dumps(arguments, ensure_ascii=False),
                    ),
                )
            )

        return calls

    @staticmethod
    def _looks_like_dsml_tool_call(content: Optional[str]) -> bool:
        return bool(content and "DSML" in content and "invoke" in content)

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
        for round_index in range(3):
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
            native_tool_calls = assistant_message.tool_calls or []
            fallback_tool_calls = (
                self._extract_dsml_tool_calls(
                    assistant_message.content,
                    round_index,
                )
                if not native_tool_calls
                else []
            )
            tool_calls = native_tool_calls or fallback_tool_calls

            # 模型没有继续调用工具，说明它已形成最终答案。
            if not tool_calls:
                answer = assistant_message.content or "暂时无法生成回答，请稍后重试。"
                if self._looks_like_dsml_tool_call(answer):
                    answer = self.INCOMPLETE_EVIDENCE_ANSWER
                return AgentRunResult(
                    answer=answer,
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
                    # DSML 是文本协议而非自然语言，不再原样写回模型上下文。
                    "content": None if fallback_tool_calls else assistant_message.content,
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
            search_was_called = False
            search_has_results = False
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
                if tool_call.function.name == "search_knowledge":
                    search_was_called = True
                    search_has_results = (
                        search_has_results
                        or tool_result.get("result_count", 0) > 0
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

            if search_was_called and not search_has_results:
                return AgentRunResult(
                    answer=self.NO_EVIDENCE_ANSWER,
                    tool_calls=tool_trace,
                    sources=[],
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )

        return AgentRunResult(
            answer="已多次检索资料，但仍无法形成可靠回答，建议转人工确认。",
            tool_calls=tool_trace,
            sources=list(source_by_chunk.values()),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    async def stream(
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
    ) -> AsyncIterator[dict[str, Any]]:
        """运行 Tool Calling Agent，并把执行进度和最终模型输出以事件流形式返回。

        工具选择阶段保持非流式，保证能完整解析 function call；最终回答阶段
        使用模型原生 stream=True，因此前端看到的文本不是人为拆分的假流式。
        """
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

        yield {"type": "status", "message": "正在分析问题…"}

        # 最多三轮工具规划；模型可以先检索，再根据结果继续选择工具。
        for round_index in range(3):
            request_kwargs: dict[str, Any] = {
                "model": llm_info.model_name,
                "messages": messages,
                "tools": KNOWLEDGE_TOOLS,
                "tool_choice": "auto",
                "temperature": 0.1,
            }
            if settings.LLM_PROVIDER == "deepseek":
                request_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

            response = await llm_info.client.chat.completions.create(**request_kwargs)
            current_prompt, current_completion, current_total = extract_usage(response)
            prompt_tokens += current_prompt
            completion_tokens += current_completion
            total_tokens += current_total

            assistant_message = response.choices[0].message
            native_tool_calls = assistant_message.tool_calls or []
            fallback_tool_calls = (
                self._extract_dsml_tool_calls(
                    assistant_message.content,
                    round_index,
                )
                if not native_tool_calls
                else []
            )
            tool_calls = native_tool_calls or fallback_tool_calls

            # 已形成答复：使用第二个、无工具的模型请求把最终文本原生流式输出。
            if not tool_calls:
                if self._looks_like_dsml_tool_call(assistant_message.content):
                    yield {
                        "type": "content_reset",
                        "content": self.INCOMPLETE_EVIDENCE_ANSWER,
                    }
                    yield {
                        "type": "done",
                        "answer": self.INCOMPLETE_EVIDENCE_ANSWER,
                        "tool_calls": tool_trace,
                        "sources": list(source_by_chunk.values()),
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                    }
                    return

                yield {"type": "status", "message": "正在生成答复…"}
                final_request_kwargs: dict[str, Any] = {
                    "model": llm_info.model_name,
                    "messages": [
                        *messages,
                        {"role": "system", "content": self.FINAL_ANSWER_PROMPT},
                    ],
                    "temperature": 0.1,
                    "stream": True,
                }
                if settings.LLM_PROVIDER == "deepseek":
                    final_request_kwargs["extra_body"] = {
                        "thinking": {"type": "disabled"}
                    }

                stream_response = await llm_info.client.chat.completions.create(
                    **final_request_kwargs
                )
                answer_parts: list[str] = []
                protocol_buffer = ""
                protocol_detected = False
                async for chunk in stream_response:
                    if not chunk.choices:
                        continue
                    content = getattr(chunk.choices[0].delta, "content", None)
                    if content:
                        protocol_buffer += content
                        if self._looks_like_dsml_tool_call(protocol_buffer):
                            protocol_detected = True
                            answer_parts = [self.INCOMPLETE_EVIDENCE_ANSWER]
                            yield {
                                "type": "content_reset",
                                "content": self.INCOMPLETE_EVIDENCE_ANSWER,
                            }
                            break
                        answer_parts.append(content)
                        yield {"type": "content", "content": content}

                # 个别兼容接口可能未返回任何 SSE 文本，降级使用规划阶段的完整答复。
                if not answer_parts and assistant_message.content and not protocol_detected:
                    answer_parts.append(assistant_message.content)
                    yield {"type": "content", "content": assistant_message.content}

                yield {
                    "type": "done",
                    "answer": "".join(answer_parts)
                    or "暂时无法生成回答，请稍后重试。",
                    "tool_calls": tool_trace,
                    "sources": list(source_by_chunk.values()),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                }
                return

            messages.append(
                {
                    "role": "assistant",
                    # DSML 是文本协议而非自然语言，不再原样写回模型上下文。
                    "content": None if fallback_tool_calls else assistant_message.content,
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

            search_was_called = False
            search_has_results = False
            for tool_call in tool_calls:
                yield {
                    "type": "status",
                    "message": self._tool_status(tool_call.function.name),
                }
                try:
                    arguments = json.loads(tool_call.function.arguments)
                    if not isinstance(arguments, dict):
                        raise ValueError("工具参数必须是 JSON 对象。")
                except (json.JSONDecodeError, ValueError) as error:
                    arguments = {}
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

                if tool_call.function.name == "search_knowledge":
                    search_was_called = True
                    search_has_results = (
                        search_has_results
                        or tool_result.get("result_count", 0) > 0
                    )

                tool_trace.append(
                    {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    }
                )
                yield {
                    "type": "tool",
                    "name": tool_call.function.name,
                    "arguments": arguments,
                }

                for source in tool_result.get("results", []):
                    key = (source["document_id"], source["chunk_index"])
                    source_by_chunk[key] = source

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )

            if search_was_called and not search_has_results:
                yield {
                    "type": "status",
                    "message": "未检索到可确认资料，正在生成安全提示…",
                }
                yield {
                    "type": "content",
                    "content": self.NO_EVIDENCE_ANSWER,
                }
                yield {
                    "type": "done",
                    "answer": self.NO_EVIDENCE_ANSWER,
                    "tool_calls": tool_trace,
                    "sources": [],
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                }
                return

        yield {
            "type": "done",
            "answer": "已多次检索资料，但仍无法形成可靠回答，建议转人工确认。",
            "tool_calls": tool_trace,
            "sources": list(source_by_chunk.values()),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
