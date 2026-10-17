from app.models.user import User


def _create_admin_and_get_headers(client, db_session):
    email = "knowledge-admin@example.com"
    password = "password123"

    create_response = client.post(
        "/api/v1/users/",
        json={
            "username": "knowledge-admin",
            "email": email,
            "password": password,
        },
    )
    assert create_response.status_code == 201

    user_id = create_response.json()["id"]
    user = db_session.get(User, user_id)
    user.is_superuser = True
    db_session.commit()

    login_response = client.post(
        "/api/v1/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_knowledge_update_full_flow(client, db_session):
    headers = _create_admin_and_get_headers(
        client,
        db_session,
    )

    # 1. 创建草稿
    create_response = client.post(
        "/api/v1/knowledge-updates/",
        headers=headers,
        json={
            "title": "车险理赔规则",
            "summary": "测试知识更新流程",
            "content": "客户申请理赔后，应按要求提交材料。",
            "category": "claims",
            "priority": "important",
            "version": "1.0",
        },
    )

    assert create_response.status_code == 201
    knowledge_update_id = create_response.json()["id"]
    assert create_response.json()["status"] == "draft"

    # 2. 编辑草稿
    update_response = client.patch(
        f"/api/v1/knowledge-updates/{knowledge_update_id}",
        headers=headers,
        json={
            "title": "车险理赔材料提交规则",
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["title"] == "车险理赔材料提交规则"

    # 3. 发布
    publish_response = client.post(
        f"/api/v1/knowledge-updates/{knowledge_update_id}/publish",
        headers=headers,
    )

    assert publish_response.status_code == 200
    assert publish_response.json()["status"] == "published"
    assert publish_response.json()["published_at"] is not None

    # 4. 已发布知识禁止继续编辑
    locked_response = client.patch(
        f"/api/v1/knowledge-updates/{knowledge_update_id}",
        headers=headers,
        json={"title": "不应该修改成功"},
    )

    assert locked_response.status_code == 409
    assert locked_response.json()["code"] == 2002

    # 5. 查询时初始状态为未读
    list_response = client.get(
        "/api/v1/knowledge-updates/",
        headers=headers,
    )

    assert list_response.status_code == 200
    item = list_response.json()[0]
    assert item["id"] == knowledge_update_id
    assert item["is_read"] is False
    assert item["read_at"] is None

    # 6. 连续标记两次，必须返回同一条阅读记录
    first_read = client.post(
        f"/api/v1/knowledge-updates/{knowledge_update_id}/read",
        headers=headers,
    )
    second_read = client.post(
        f"/api/v1/knowledge-updates/{knowledge_update_id}/read",
        headers=headers,
    )

    assert first_read.status_code == 200
    assert second_read.status_code == 200
    assert first_read.json()["id"] == second_read.json()["id"]

    # 7. 再次查询时状态变为已读
    final_list = client.get(
        "/api/v1/knowledge-updates/",
        headers=headers,
    )

    final_item = final_list.json()[0]
    assert final_item["is_read"] is True
    assert final_item["read_at"] is not None
