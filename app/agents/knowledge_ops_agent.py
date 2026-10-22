import json
import operator
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents.knowledge_ops_tools import (
    get_document_status_summary,
    get_knowledge_update_summary,
    get_llm_runtime_summary,
)
from app.core.config import settings
from app.services.llm_service import get_llm_client


class OpsPlanStep(TypedDict):
    """运营 Agent 计划中的一个可执行步骤。"""

    id: str
    task: str
    tool_name: str
    tool_arguments: dict[str, Any]


class OpsStepResult(TypedDict):
    """某个步骤执行后的可追踪结果。"""

    step_id: str
    task: str
    tool_name: str
    result: dict[str, Any]


class KnowledgeOpsState(TypedDict):
    """LangGraph 中各节点共享的任务状态。"""

    input: str
    owner_id: int
    plan: list[OpsPlanStep]
    past_steps: Annotated[list[OpsStepResult], operator.add]
    errors: Annotated[list[str], operator.add]
    response: str


OPS_READ_TOOL_NAMES = {
    "get_document_status_summary",
    "get_knowledge_update_summary",
    "get_llm_runtime_summary",
}

OPS_PLAN_PARAMETERS = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "task": {"type": "string"},
                    "tool_name": {
                        "type": "string",
                        "enum": sorted(OPS_READ_TOOL_NAMES),
                    },
                    "tool_arguments": {
                        "type": "object",
                        "additionalProperties": False,
                    },
                },
                "required": [
                    "id",
                    "task",
                    "tool_name",
                    "tool_arguments",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["steps"],
    "additionalProperties": False,
}

OPS_PLANNER_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "submit_ops_plan",
            "description": "提交知识库运营巡检的只读执行计划。",
            "parameters": OPS_PLAN_PARAMETERS,
        },
    },
]

OPS_RECOVERY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "submit_recovery_plan",
            "description": "在某个巡检步骤失败后，提交剩余的只读恢复计划。",
            "parameters": OPS_PLAN_PARAMETERS,
        },
    },
]

OPS_TOOL_HANDLERS = {
    "get_document_status_summary": get_document_status_summary,
    "get_knowledge_update_summary": get_knowledge_update_summary,
    "get_llm_runtime_summary": get_llm_runtime_summary,
}


def _default_health_check_plan() -> list[OpsPlanStep]:
    """模型规划失败时使用的安全降级计划。"""

    return [
        {
            "id": "document_health",
            "task": "检查知识库文档处理状态与失败任务",
            "tool_name": "get_document_status_summary",
            "tool_arguments": {},
        },
        {
            "id": "update_reading",
            "task": "检查已发布知识更新与未读情况",
            "tool_name": "get_knowledge_update_summary",
            "tool_arguments": {},
        },
        {
            "id": "llm_runtime",
            "task": "检查过去 24 小时 LLM 调用质量",
            "tool_name": "get_llm_runtime_summary",
            "tool_arguments": {},
        },
    ]


def _sanitize_plan(raw_steps: Any) -> list[OpsPlanStep]:
    """校验模型计划，防止它调用未登记或带危险参数的工具。"""

    if not isinstance(raw_steps, list):
        raise ValueError("计划 steps 必须是列表。")

    steps: list[OpsPlanStep] = []
    for index, raw_step in enumerate(raw_steps[:3], start=1):
        if not isinstance(raw_step, dict):
            raise ValueError("计划步骤必须是对象。")

        tool_name = raw_step.get("tool_name")
        task = raw_step.get("task")
        tool_arguments = raw_step.get("tool_arguments", {})

        if tool_name not in OPS_READ_TOOL_NAMES:
            raise ValueError(f"不允许调用工具：{tool_name}")
        if not isinstance(task, str) or not task.strip():
            raise ValueError("计划步骤缺少 task。")
        if tool_arguments != {}:
            raise ValueError("当前只读工具不接受模型传入的参数。")

        steps.append(
            {
                "id": str(raw_step.get("id") or f"step_{index}"),
                "task": task.strip(),
                "tool_name": tool_name,
                "tool_arguments": {},
            }
        )

    if not steps:
        raise ValueError("计划不能为空。")
    return steps


def _with_deepseek_thinking_disabled(
    request_kwargs: dict[str, Any],
) -> dict[str, Any]:
    """让 DeepSeek 使用兼容 Tool Calling 的非思考模式。"""

    if settings.LLM_PROVIDER == "deepseek":
        request_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    return request_kwargs


async def planner(state: KnowledgeOpsState) -> dict[str, Any]:
    """让 LLM 生成只读巡检计划；失败时安全降级。"""

    messages = [
        {
            "role": "system",
            "content": (
                "你是保知通的知识运营规划 Agent。"
                "将用户的运营巡检诉求拆解为 1 到 3 个只读步骤。"
                "只能使用提供的工具，不能创建、发布、删除或修改数据。"
                "必须调用 submit_ops_plan 提交计划。"
            ),
        },
        {"role": "user", "content": state["input"]},
    ]

    try:
        llm_info = get_llm_client()
        request_kwargs = _with_deepseek_thinking_disabled(
            {
                "model": llm_info.model_name,
                "messages": messages,
                "tools": OPS_PLANNER_TOOL,
                "tool_choice": {
                    "type": "function",
                    "function": {"name": "submit_ops_plan"},
                },
                "temperature": 0.1,
            }
        )
        llm_response = await llm_info.client.chat.completions.create(
            **request_kwargs
        )
        tool_calls = llm_response.choices[0].message.tool_calls or []
        if len(tool_calls) != 1:
            raise ValueError("规划模型未返回唯一的计划工具调用。")

        arguments = json.loads(tool_calls[0].function.arguments)
        return {"plan": _sanitize_plan(arguments.get("steps"))}
    except Exception as error:
        return {
            "plan": _default_health_check_plan(),
            "errors": [f"LLM 规划失败，已使用安全降级计划：{error}"],
        }


def build_executor(db: Session):
    """为当前请求创建一个绑定数据库会话的执行节点。"""

    async def executor(state: KnowledgeOpsState) -> dict[str, Any]:
        plan = state.get("plan", [])
        if not plan:
            return {"errors": ["执行器收到空计划，无法继续执行。"]}

        current_step = plan[0]
        remaining_plan = plan[1:]
        tool_name = current_step["tool_name"]
        tool_handler = OPS_TOOL_HANDLERS.get(tool_name)
        if tool_handler is None:
            return {
                "plan": remaining_plan,
                "errors": [f"未注册的运营工具：{tool_name}"],
            }

        try:
            result = tool_handler(db=db, owner_id=state["owner_id"])
            step_result: OpsStepResult = {
                "step_id": current_step["id"],
                "task": current_step["task"],
                "tool_name": tool_name,
                "result": result,
            }
            return {"plan": remaining_plan, "past_steps": [step_result]}
        except Exception as error:
            step_result: OpsStepResult = {
                "step_id": current_step["id"],
                "task": current_step["task"],
                "tool_name": tool_name,
                "result": {"error": str(error)},
            }
            return {
                "plan": remaining_plan,
                "past_steps": [step_result],
                "errors": [f"步骤 {current_step['id']} 执行失败：{error}"],
            }

    return executor


async def replanner(state: KnowledgeOpsState) -> dict[str, Any]:
    """仅在工具失败时，请 LLM 调整剩余的只读计划。"""

    plan = state.get("plan", [])
    past_steps = state.get("past_steps", [])
    if not plan:
        return {}
    if len(past_steps) >= 3:
        return {
            "plan": [],
            "errors": ["已达到最多 3 个执行步骤的安全上限。"],
        }

    last_result = past_steps[-1]["result"] if past_steps else {}
    if "error" not in last_result:
        return {}

    try:
        llm_info = get_llm_client()
        messages = [
            {
                "role": "system",
                "content": (
                    "你是保知通的知识运营恢复规划 Agent。"
                    "刚刚有一个只读巡检步骤失败。"
                    "只从剩余可用的只读工具中选择后续步骤，"
                    "不得创建、发布、删除或修改数据。"
                    "必须调用 submit_recovery_plan。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"已执行步骤：{json.dumps(past_steps, ensure_ascii=False)}\n"
                    f"当前剩余计划：{json.dumps(plan, ensure_ascii=False)}"
                ),
            },
        ]
        request_kwargs = _with_deepseek_thinking_disabled(
            {
                "model": llm_info.model_name,
                "messages": messages,
                "tools": OPS_RECOVERY_TOOL,
                "tool_choice": {
                    "type": "function",
                    "function": {"name": "submit_recovery_plan"},
                },
                "temperature": 0.1,
            }
        )
        llm_response = await llm_info.client.chat.completions.create(
            **request_kwargs
        )
        tool_calls = llm_response.choices[0].message.tool_calls or []
        if len(tool_calls) != 1:
            raise ValueError("恢复规划未返回唯一工具调用。")

        arguments = json.loads(tool_calls[0].function.arguments)
        revised_plan = _sanitize_plan(arguments.get("steps"))
        return {"plan": revised_plan[: 3 - len(past_steps)]}
    except Exception as error:
        return {"errors": [f"恢复规划失败，保留原计划继续执行：{error}"]}


def _fallback_report(state: KnowledgeOpsState) -> str:
    """模型不可用时生成最基础的巡检报告。"""

    lines = ["知识库运营巡检已完成。"]
    for step in state.get("past_steps", []):
        result = step["result"]
        if "error" in result:
            lines.append(f"- {step['task']}：执行失败，原因：{result['error']}")
        else:
            lines.append(f"- {step['task']}：已完成。")
    if state.get("errors"):
        lines.append("存在异常记录，请在后台日志中进一步核对。")
    return "\n".join(lines)


async def reporter(state: KnowledgeOpsState) -> dict[str, Any]:
    """根据全部工具结果生成面向运营人员的报告。"""

    try:
        llm_info = get_llm_client()
        messages = [
            {
                "role": "system",
                "content": (
                    "你是保知通的知识库运营报告 Agent。"
                    "请仅依据给出的巡检结果生成简洁报告，包括文档健康度、"
                    "知识更新阅读情况、LLM 调用质量和需关注的风险。"
                    "不得虚构未提供的数据；没有问题时明确说明。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"原始任务：{state['input']}\n"
                    f"执行结果：{json.dumps(state.get('past_steps', []), ensure_ascii=False)}\n"
                    f"异常记录：{json.dumps(state.get('errors', []), ensure_ascii=False)}"
                ),
            },
        ]
        request_kwargs = _with_deepseek_thinking_disabled(
            {
                "model": llm_info.model_name,
                "messages": messages,
                "temperature": 0.2,
            }
        )
        llm_response = await llm_info.client.chat.completions.create(
            **request_kwargs
        )
        response = llm_response.choices[0].message.content
        if not response:
            raise ValueError("报告模型返回为空。")
        return {"response": response}
    except Exception as error:
        return {
            "response": _fallback_report(state),
            "errors": [f"报告生成失败，已使用降级报告：{error}"],
        }


class KnowledgeOpsAgent:
    """知识库运营 Agent 的 LangGraph 编排入口。"""

    def __init__(self, db: Session):
        self.db = db
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(KnowledgeOpsState)
        workflow.add_node("planner", planner)
        workflow.add_node("executor", build_executor(self.db))
        workflow.add_node("replanner", replanner)
        workflow.add_node("reporter", reporter)

        workflow.set_entry_point("planner")
        workflow.add_edge("planner", "executor")
        workflow.add_edge("executor", "replanner")

        def choose_next_node(state: KnowledgeOpsState) -> str:
            return "executor" if state.get("plan") else "reporter"

        workflow.add_conditional_edges(
            "replanner",
            choose_next_node,
            {"executor": "executor", "reporter": "reporter"},
        )
        workflow.add_edge("reporter", END)
        return workflow.compile(checkpointer=MemorySaver())

    async def run(
        self,
        *,
        user_input: str,
        owner_id: int,
        session_id: str,
    ) -> dict[str, Any]:
        """运行一次完整的计划、执行、重规划和报告生成。"""

        initial_state: KnowledgeOpsState = {
            "input": user_input,
            "owner_id": owner_id,
            "plan": [],
            "past_steps": [],
            "errors": [],
            "response": "",
        }
        return await self.graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": session_id}},
        )
