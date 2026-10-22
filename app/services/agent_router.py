from dataclasses import dataclass
from typing import Literal


AgentName = Literal[
    "after_sales_qa",
    "claims_guidance",
    "policy_service",
    "complaint_escalation",
    "compliance_guard",
]


@dataclass(frozen=True)
class AgentDecision:
    """一次问题路由的结果。"""

    agent_name: AgentName
    display_name: str
    instruction: str


def route_agent(query: str) -> AgentDecision:
    """根据客服问题选择最合适的领域 Agent。"""
    normalized_query = query.strip().lower()

    # 高风险投诉优先于一般业务咨询。
    if any(keyword in normalized_query for keyword in ("投诉", "监管", "消协", "媒体曝光")):
        return AgentDecision(
            agent_name="complaint_escalation",
            display_name="投诉升级 Agent",
            instruction="识别投诉风险，提示客服记录诉求、核实事实并按流程升级，不承诺处理结果。",
        )

    # 合规风险优先于业务解释。
    if any(keyword in normalized_query for keyword in ("违规", "违法", "免责", "隐瞒", "误导销售")):
        return AgentDecision(
            agent_name="compliance_guard",
            display_name="合规风控 Agent",
            instruction="优先提示合规边界，不编造规则，不给出超权限承诺。",
        )

    if any(keyword in normalized_query for keyword in ("理赔", "报案", "定损", "拒赔", "赔付")):
        return AgentDecision(
            agent_name="claims_guidance",
            display_name="理赔服务 Agent",
            instruction="说明理赔流程、所需材料与处理节点，不承诺赔付金额或理赔结论。",
        )

    if any(keyword in normalized_query for keyword in ("退保", "缴费", "续保", "保单变更", "受益人", "地址变更")):
        return AgentDecision(
            agent_name="policy_service",
            display_name="保单服务 Agent",
            instruction="说明保单售后办理条件、所需信息和服务流程，不替代人工完成业务操作。",
        )

    return AgentDecision(
        agent_name="after_sales_qa",
        display_name="售后知识问答 Agent",
        instruction="基于检索到的知识资料回答，并明确引用来源；不确定时建议转人工确认。",
    )