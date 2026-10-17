from datetime import datetime, timezone
from typing import List

from fastapi import status
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.knowledge_update import KnowledgeUpdate, KnowledgeUpdateRead
from app.schemas.knowledge_update import (
    KnowledgeUpdateCreate,
    KnowledgeUpdateOut,
    KnowledgeUpdateUpdate,
)
from app.utils.errors import AppException


class KnowledgeUpdateService:
    """知识更新业务逻辑。"""

    @staticmethod
    def get_or_404(
        db: Session,
        knowledge_update_id: int,
    ) -> KnowledgeUpdate:
        """按主键查询知识更新，不存在时抛出 404。"""

        knowledge_update = db.get(
            KnowledgeUpdate,
            knowledge_update_id,
        )

        if knowledge_update is None:
            raise AppException(
                code=2001,
                msg="Knowledge update not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return knowledge_update

    @staticmethod
    def create_update(
        db: Session,
        update_in: KnowledgeUpdateCreate,
        creator_id: int,
    ) -> KnowledgeUpdate:
        """创建知识更新草稿。"""

        knowledge_update = KnowledgeUpdate(
            **update_in.model_dump(),
            status="draft",
            created_by_id=creator_id,
        )

        try:
            db.add(knowledge_update)
            db.commit()
            db.refresh(knowledge_update)
        except Exception:
            db.rollback()
            raise

        return knowledge_update

    @staticmethod
    def update_draft(
        db: Session,
        knowledge_update_id: int,
        update_in: KnowledgeUpdateUpdate,
    ) -> KnowledgeUpdate:
        """修改一条尚未发布的知识更新。"""

        knowledge_update = KnowledgeUpdateService.get_or_404(
            db,
            knowledge_update_id,
        )

        if knowledge_update.status != "draft":
            raise AppException(
                code=2002,
                msg="Only draft knowledge updates can be edited",
                status_code=status.HTTP_409_CONFLICT,
            )

        update_data = update_in.model_dump(
            exclude_unset=True,
            exclude_none=True,
        )

        for field, value in update_data.items():
            setattr(knowledge_update, field, value)

        try:
            db.commit()
            db.refresh(knowledge_update)
        except Exception:
            db.rollback()
            raise

        return knowledge_update

    @staticmethod
    def publish_update(
        db: Session,
        knowledge_update_id: int,
    ) -> KnowledgeUpdate:
        """发布一条草稿状态的知识更新。"""

        knowledge_update = KnowledgeUpdateService.get_or_404(
            db,
            knowledge_update_id,
        )

        if knowledge_update.status != "draft":
            raise AppException(
                code=2003,
                msg="Only draft knowledge updates can be published",
                status_code=status.HTTP_409_CONFLICT,
            )

        knowledge_update.status = "published"
        knowledge_update.published_at = datetime.now(timezone.utc)

        try:
            db.commit()
            db.refresh(knowledge_update)
        except Exception:
            db.rollback()
            raise

        return knowledge_update

    @staticmethod
    def list_published_for_user(
        db: Session,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[KnowledgeUpdateOut]:
        """查询已发布知识以及当前用户的阅读状态。"""

        statement = (
            select(
                KnowledgeUpdate,
                KnowledgeUpdateRead,
            )
            .outerjoin(
                KnowledgeUpdateRead,
                and_(
                    KnowledgeUpdateRead.knowledge_update_id
                    == KnowledgeUpdate.id,
                    KnowledgeUpdateRead.user_id == user_id,
                ),
            )
            .where(KnowledgeUpdate.status == "published")
            .order_by(KnowledgeUpdate.published_at.desc())
            .offset(skip)
            .limit(limit)
        )

        rows = db.execute(statement).all()
        result: List[KnowledgeUpdateOut] = []

        for knowledge_update, read_record in rows:
            item = KnowledgeUpdateOut.model_validate(knowledge_update)
            item.is_read = read_record is not None
            item.read_at = (
                read_record.read_at
                if read_record is not None
                else None
            )

            result.append(item)

        return result

    @staticmethod
    def mark_as_read(
        db: Session,
        knowledge_update_id: int,
        user_id: int,
    ) -> KnowledgeUpdateRead:
        """将已发布的知识标记为当前用户已读。"""

        knowledge_update = KnowledgeUpdateService.get_or_404(
            db,
            knowledge_update_id,
        )

        if knowledge_update.status != "published":
            raise AppException(
                code=2004,
                msg="Only published knowledge can be read",
                status_code=status.HTTP_409_CONFLICT,
            )

        read_statement = select(KnowledgeUpdateRead).where(
            KnowledgeUpdateRead.knowledge_update_id
            == knowledge_update_id,
            KnowledgeUpdateRead.user_id == user_id,
        )

        existing_read = db.execute(
            read_statement,
        ).scalar_one_or_none()

        if existing_read is not None:
            return existing_read

        read_record = KnowledgeUpdateRead(
            knowledge_update_id=knowledge_update_id,
            user_id=user_id,
        )

        try:
            db.add(read_record)
            db.commit()
            db.refresh(read_record)
        except IntegrityError:
            db.rollback()

            existing_read = db.execute(
                read_statement,
            ).scalar_one_or_none()

            if existing_read is not None:
                return existing_read

            raise
        except Exception:
            db.rollback()
            raise

        return read_record
