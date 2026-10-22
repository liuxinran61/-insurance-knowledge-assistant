from dataclasses import dataclass
from typing import Literal

from app.services.rag_service import RAGService


ClaimStage = Literal[
    "reporting",
    "materials",
    "reviewing",
    "dispute",
    "unknown",
]


@dataclass
class ClaimsGuidanceResult:
    stage: ClaimStage
    next_steps: list[str]
    handoff_required: bool
    handoff_reason: str | None
    source_filenames: list[str]


class ClaimsGuidanceAgent:
    """理赔服务 Agent：调用检索工具并输出客服下一步动作。"""

    def __init__(self, rag_service: RAGService):
        self.rag_service = rag_service

    @staticmethod
    def identify_stage(query: str) -> ClaimStage:
        normalized_query = query.lower()

        if any(keyword in normalized_query for keyword in ("拒赔", "不赔", "争议", "投诉")):
            return "dispute"
        if any(keyword in normalized_query for keyword in ("补材料", "资料", "发票", "病历")):
            return "materials"
        if any(keyword in normalized_query for keyword in ("审核", "定损", "处理中", "进度")):
            return "reviewing"
        if any(keyword in normalized_query for keyword in ("报案", "出险", "申请理赔")):
            return "reporting"
        return "unknown"

    @staticmethod
    def build_next_steps(stage: ClaimStage) -> list[str]:
        step_map = {
            "reporting": [
                "确认出险时间、地点、经过和客户联系方式。",
                "引导客户按产品规则完成报案，并告知后续材料要求。",
            ],
            "materials": [
                "核对已提交材料与待补材料清单。",
                "说明材料用途和提交渠道，不承诺审核或赔付结果。",
            ],
            "reviewing": [
                "告知客户案件正在审核或定损中的当前状态。",
                "说明处理节点，并提醒以实际审核结果为准。",
            ],
            "dispute": [
                "记录客户争议点、诉求和已沟通事实。",
                "不要承诺赔付结论；按投诉或争议流程升级人工处理。",
            ],
            "unknown": [
                "先确认保单、出险和当前理赔进度等基础信息。",
                "根据知识库资料向客户说明下一步处理流程。",
            ],
        }
        return step_map[stage]

    async def run(self, query: str, owner_id: int) -> ClaimsGuidanceResult:
        """执行理赔 Agent 工作流，并调用 RAG 作为检索工具。"""
        stage = self.identify_stage(query)

        chunks = await self.rag_service.retrieve_relevant_chunks(
            query=query,
            owner_id=owner_id,
            top_k=3,
        )
        source_filenames = sorted({chunk.document.filename for chunk in chunks})

        handoff_required = stage == "dispute"
        handoff_reason = (
            "涉及拒赔、争议或投诉，需要按升级流程转人工处理。"
            if handoff_required
            else None
        )

        return ClaimsGuidanceResult(
            stage=stage,
            next_steps=self.build_next_steps(stage),
            handoff_required=handoff_required,
            handoff_reason=handoff_reason,
            source_filenames=source_filenames,
        )