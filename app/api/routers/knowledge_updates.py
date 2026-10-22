from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_active_superuser,
    get_current_active_user,
    get_db,
)
from app.models.user import User
from app.schemas.knowledge_update import (
    KnowledgeUpdateCreate,
    KnowledgeUpdateOut,
    KnowledgeUpdateReadOut,
    KnowledgeUpdateUpdate,
)
from app.services.knowledge_update_service import KnowledgeUpdateService


router = APIRouter()


@router.get(
    "/",
    response_model=List[KnowledgeUpdateOut],
    summary="获取已发布知识列表",
)
async def list_published_knowledge_updates(
    skip: int = Query(
        0,
        ge=0,
        description="跳过前 N 条数据",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=100,
        description="本次最多返回多少条数据",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取已发布知识，并返回当前用户的阅读状态。"""

    return KnowledgeUpdateService.list_published_for_user(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/admin",
    response_model=List[KnowledgeUpdateOut],
    summary="管理员获取全部知识更新",
)
async def list_all_knowledge_updates_for_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_active_superuser),
):
    """管理员查看草稿、已发布和已归档的全部知识更新。"""

    return KnowledgeUpdateService.list_all_for_admin(
        db=db,
        skip=skip,
        limit=limit,
    )

@router.post(
    "/",
    response_model=KnowledgeUpdateOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建知识更新草稿",
)
async def create_knowledge_update(
    update_in: KnowledgeUpdateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_active_superuser,
    ),
):
    """由管理员创建一条知识更新草稿。"""

    return KnowledgeUpdateService.create_update(
        db=db,
        update_in=update_in,
        creator_id=current_user.id,
    )


@router.patch(
    "/{knowledge_update_id}",
    response_model=KnowledgeUpdateOut,
    summary="编辑知识更新草稿",
)
async def update_knowledge_update_draft(
    knowledge_update_id: int,
    update_in: KnowledgeUpdateUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_active_superuser),
):
    """由管理员修改一条草稿状态的知识更新。"""

    return KnowledgeUpdateService.update_draft(
        db=db,
        knowledge_update_id=knowledge_update_id,
        update_in=update_in,
    )


@router.post(
    "/{knowledge_update_id}/publish",
    response_model=KnowledgeUpdateOut,
    summary="发布知识更新",
)
async def publish_knowledge_update(
    knowledge_update_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(
        get_current_active_superuser,
    ),
):
    """由管理员发布一条草稿状态的知识更新。"""

    return KnowledgeUpdateService.publish_update(
        db=db,
        knowledge_update_id=knowledge_update_id,
    )


@router.post(
    "/{knowledge_update_id}/read",
    response_model=KnowledgeUpdateReadOut,
    summary="标记知识更新为已读",
)
async def mark_knowledge_update_as_read(
    knowledge_update_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_active_user,
    ),
):
    """将一条已发布知识标记为当前客服已读。"""

    return KnowledgeUpdateService.mark_as_read(
        db=db,
        knowledge_update_id=knowledge_update_id,
        user_id=current_user.id,
    )
