import uuid

import pytest

from app.agents.knowledge_ops_agent import _fallback_report, _sanitize_plan
from app.api.routers import knowledge_ops
from app.models.user import User


def _register_and_login(client, db_session, *, is_superuser: bool):
    email = f"ops-{uuid.uuid4().hex[:8]}@example.com"
    password = "password123"

    create_response = client.post(
        "/api/v1/users/",
        json={
            "username": f"ops-{uuid.uuid4().hex[:8]}",
            "email": email,
            "password": password,
        },
    )
    assert create_response.status_code == 201

    user = db_session.get(User, create_response.json()["id"])
    user.is_superuser = is_superuser
    db_session.commit()

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert login_response.status_code == 200
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


def test_sanitize_plan_rejects_unregistered_tool():
    with pytest.raises(ValueError, match="不允许调用工具"):
        _sanitize_plan(
            [
                {
                    "id": "unsafe",
                    "task": "删除所有资料",
                    "tool_name": "delete_all_documents",
                    "tool_arguments": {},
                }
            ]
        )


def test_fallback_report_includes_failed_step():
    report = _fallback_report(
        {
            "input": "检查知识库",
            "owner_id": 1,
            "plan": [],
            "past_steps": [
                {
                    "step_id": "document_health",
                    "task": "检查文档状态",
                    "tool_name": "get_document_status_summary",
                    "result": {"error": "数据库暂不可用"},
                }
            ],
            "errors": ["步骤 document_health 执行失败"],
            "response": "",
        }
    )

    assert "执行失败" in report
    assert "数据库暂不可用" in report


def test_knowledge_ops_endpoint_requires_admin(client, db_session):
    headers = _register_and_login(client, db_session, is_superuser=False)

    response = client.post(
        "/api/v1/knowledge-ops/run",
        headers=headers,
        json={"query": "请检查知识库运行情况"},
    )

    assert response.status_code == 403


def test_knowledge_ops_endpoint_returns_agent_result(client, db_session, monkeypatch):
    headers = _register_and_login(client, db_session, is_superuser=True)

    class FakeKnowledgeOpsAgent:
        def __init__(self, db):
            self.db = db

        async def run(self, *, user_input, owner_id, session_id):
            return {
                "response": "巡检完成：文档状态正常。",
                "past_steps": [
                    {
                        "step_id": "document_health",
                        "task": "检查文档状态",
                        "tool_name": "get_document_status_summary",
                        "result": {"total_documents": 3},
                    }
                ],
                "errors": [],
            }

    monkeypatch.setattr(
        knowledge_ops,
        "KnowledgeOpsAgent",
        FakeKnowledgeOpsAgent,
    )

    response = client.post(
        "/api/v1/knowledge-ops/run",
        headers=headers,
        json={"query": "请检查知识库运行情况"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["response"] == "巡检完成：文档状态正常。"
    assert payload["errors"] == []
    assert payload["steps"][0]["tool_name"] == "get_document_status_summary"
    assert payload["session_id"].startswith("ops-")
