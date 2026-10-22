from typing import Any

from pydantic import BaseModel, Field


class KnowledgeOpsRunRequest(BaseModel):
    """触发一次知识库运营巡检的请求。"""

    query: str = Field(
        "请检查知识库运行情况",
        min_length=1,
        max_length=500,
        description="运营人员的巡检诉求",
    )


class KnowledgeOpsStepOut(BaseModel):
    """一个已经执行完成的巡检步骤。"""

    step_id: str
    task: str
    tool_name: str
    result: dict[str, Any]


class KnowledgeOpsRunResponse(BaseModel):
    """知识运营 Agent 的完整执行结果。"""

    session_id: str
    response: str
    steps: list[KnowledgeOpsStepOut]
    errors: list[str]