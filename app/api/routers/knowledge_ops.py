from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.knowledge_ops_agent import KnowledgeOpsAgent
from app.api.deps import get_current_active_superuser, get_db
from app.models.user import User
from app.schemas.knowledge_ops import (
    KnowledgeOpsRunRequest,
    KnowledgeOpsRunResponse,
)

router = APIRouter()


@router.post(
    "/run",
    response_model=KnowledgeOpsRunResponse,
    summary="运行知识库运营巡检 Agent",
)
async def run_knowledge_ops_agent(
    request: KnowledgeOpsRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """管理员发起一次只读的知识库运营巡检。"""

    session_id = f"ops-{current_user.id}-{uuid4().hex}"
    agent = KnowledgeOpsAgent(db)

    final_state = await agent.run(
        user_input=request.query,
        owner_id=current_user.id,
        session_id=session_id,
    )

    return KnowledgeOpsRunResponse(
        session_id=session_id,
        response=final_state.get("response", ""),
        steps=final_state.get("past_steps", []),
        errors=final_state.get("errors", []),
    )