"""为项目内置的保险样例资料补齐结构化元数据。

该脚本只匹配 METADATA_BY_FILENAME 中的文件名，并且仅填充当前为空的字段，
可以重复执行，不会覆盖后续人工维护过的元数据。
"""

from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.document import Document


EFFECTIVE_AT = datetime(2026, 10, 20, tzinfo=timezone.utc)

METADATA_BY_FILENAME = {
    "auto-claims-v1.md": ("auto_insurance", "安心行车险（演示产品）", "1.0"),
    "auto-roadside-v1.md": ("auto_insurance", "安心行车险（演示产品）", "1.0"),
    "health-claims-v1.md": ("health_insurance", "安心住院医疗险（演示产品）", "1.0"),
    "travel-emergency-v1.md": ("travel_insurance", "安心出行旅行险（演示产品）", "1.0"),
    "home-claims-v1.md": ("property_insurance", "安心家财险（演示产品）", "1.0"),
    "life-policy-service-v1.md": ("life_insurance", "安心守护人身险（演示产品）", "1.0"),
    "service-change-v1.md": ("policy_service", "通用服务规则（演示资料）", "1.0"),
    "policy-payment-v1.md": ("policy_service", "通用服务规则（演示资料）", "1.0"),
    "claims-progress-v1.md": ("claims_service", "通用理赔服务规则（演示资料）", "1.0"),
    "complaint-escalation-v1.md": ("customer_service", "通用服务规则（演示资料）", "1.0"),
    "compliance-v1.md": ("compliance", "通用合规规则（演示资料）", "1.0"),
    "knowledge-boundary-v1.md": ("compliance", "通用合规规则（演示资料）", "1.0"),
}


def main() -> None:
    db = SessionLocal()
    updated_count = 0

    try:
        documents = db.execute(
            select(Document).where(Document.filename.in_(METADATA_BY_FILENAME))
        ).scalars()

        for document in documents:
            business_line, product, knowledge_version = METADATA_BY_FILENAME[document.filename]
            metadata = {
                "business_line": business_line,
                "product": product,
                "knowledge_version": knowledge_version,
                "effective_at": EFFECTIVE_AT,
            }
            changed = False

            for field, value in metadata.items():
                if getattr(document, field) is None:
                    setattr(document, field, value)
                    changed = True

            if changed:
                updated_count += 1
                print(f"已回填: {document.filename}")

        db.commit()
        print(f"回填完成，共更新 {updated_count} 份文档。")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
