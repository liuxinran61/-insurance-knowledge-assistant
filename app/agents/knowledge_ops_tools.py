from typing import Any
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.document import DOCUMENT_STATUS_FAILED, Document
from app.models.knowledge_update import (
    KnowledgeUpdate,
    KnowledgeUpdateRead,
)
from app.models.llm_call_log import LLMCallLog

def get_document_status_summary(

        db:Session,
        owner_id:int,
)->dict[str,Any]:
    """统计当前用户知识库中各文档的处理状态。"""

    status_rows=db.execute(
        select(Document.status,
               func.count(Document.id))
        .where(Document.owner_id==owner_id)
        .group_by(Document.status)
    ).all()

    status_counts={
        status:count
        for status,count in status_rows
    }

    failed_rows=db.execute(
        select(
            Document.filename,
            Document.error_message,
            Document.updated_at,
        )
    .where(
        Document.owner_id==owner_id,
        Document.status==DOCUMENT_STATUS_FAILED,
    )
    .order_by(Document.updated_at.desc())
    .limit(5)
    ).all()

    return {
        "total_documents":sum(status_counts.values()),
        "status_counts":status_counts,
        "failed_documents":[
            {
                "filename":filename,
                "error_message":error_message,
                "updated_at":updated_at.isoformat(),
            }
            for filename,error_message,updated_at in failed_rows
        ],
    }
def get_knowledge_update_summary(
    db: Session,
    owner_id: int,
) -> dict[str, Any]:
    """统计当前用户的已发布知识更新与未读情况。"""

    rows = db.execute(
        select(KnowledgeUpdate, KnowledgeUpdateRead.id)
        .outerjoin(
            KnowledgeUpdateRead,
            and_(
                KnowledgeUpdateRead.knowledge_update_id
                == KnowledgeUpdate.id,
                KnowledgeUpdateRead.user_id == owner_id,
            ),
        )
        .where(KnowledgeUpdate.status == "published")
        .order_by(KnowledgeUpdate.published_at.desc())
    ).all()

    return {
        "published_count": len(rows),
        "unread_count": sum(
            read_id is None
            for _, read_id in rows
        ),
        "recent_updates": [
            {
                "id": update.id,
                "title": update.title,
                "category": update.category,
                "priority": update.priority,
                "version": update.version,
                "published_at": (
                    update.published_at.isoformat()
                    if update.published_at
                    else None
                ),
                "is_read": read_id is not None,
            }
            for update, read_id in rows[:5]
        ],
    }

def get_llm_runtime_summary(
    db: Session,
    owner_id: int,
) -> dict[str, Any]:
    """统计当前用户过去 24 小时的 LLM 调用运行质量。"""

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    filters = (
        LLMCallLog.user_id == owner_id,
        LLMCallLog.created_at >= cutoff,
    )

    total_calls = db.scalar(
        select(func.count(LLMCallLog.id))
        .where(*filters)
    ) or 0

    failed_calls = db.scalar(
        select(func.count(LLMCallLog.id))
        .where(
            *filters,
            LLMCallLog.status != "success",
        )
    ) or 0

    avg_latency_ms = db.scalar(
        select(func.avg(LLMCallLog.latency_ms))
        .where(*filters)
    ) or 0

    total_tokens = db.scalar(
        select(func.sum(LLMCallLog.total_tokens))
        .where(*filters)
    ) or 0

    error_rows = db.execute(
        select(
            LLMCallLog.endpoint,
            LLMCallLog.error_message,
            LLMCallLog.created_at,
        )
        .where(
            *filters,
            LLMCallLog.status != "success",
        )
        .order_by(LLMCallLog.created_at.desc())
        .limit(5)
    ).all()

    return {
        "window_hours": 24,
        "total_calls": int(total_calls),
        "failed_calls": int(failed_calls),
        "failure_rate": (
            round(failed_calls / total_calls, 4)
            if total_calls
            else 0.0
        ),
        "avg_latency_ms": round(float(avg_latency_ms), 2),
        "total_tokens": int(total_tokens),
        "recent_errors": [
            {
                "endpoint": endpoint,
                "error_message": error_message,
                "created_at": created_at.isoformat(),
            }
            for endpoint, error_message, created_at in error_rows
        ],
    }