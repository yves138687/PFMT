from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.models.audit import AuditLog


def test_seeded_admin_can_login_and_read_profile(client: TestClient, auth_headers: dict[str, str]) -> None:
    """默认管理员可登录，并能用 JWT 读取当前用户。"""

    response = client.get("/api/auth/me", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert body["user_id"] == "user_admin"


def test_wrong_password_is_rejected_and_audited(client: TestClient) -> None:
    """错误密码返回 401，并记录失败登录审计。"""

    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "bad-password"},
    )

    assert response.status_code == 401
    with Session(get_engine()) as db:
        stmt = select(AuditLog).where(
            AuditLog.action_type == "login",
            AuditLog.action_result == "failed",
        )
        assert db.execute(stmt).scalar_one_or_none() is not None


def test_login_rate_limit_locks_repeated_failures(client: TestClient) -> None:
    """同一用户名和来源连续失败后会被临时限速。"""

    for _index in range(5):
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "bad-password"},
        )
        assert response.status_code == 401

    locked_response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "bad-password"},
    )
    assert locked_response.status_code == 429


def test_hidden_content_session_switch_requires_auth(client: TestClient, auth_headers: dict[str, str]) -> None:
    """显示隐藏内容必须写入当前登录会话，不能未登录打开。"""

    unauthorized_read = client.get("/api/auth/hidden-content")
    assert unauthorized_read.status_code == 401

    initial = client.get("/api/auth/hidden-content", headers=auth_headers)
    assert initial.status_code == 200
    assert initial.json()["show_hidden_enabled"] is False

    unauthorized = client.put("/api/auth/hidden-content", json={"enabled": True})
    assert unauthorized.status_code == 401

    response = client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": True},
    )
    assert response.status_code == 200
    assert response.json()["show_hidden_enabled"] is True

    persisted = client.get("/api/auth/hidden-content", headers=auth_headers)
    assert persisted.status_code == 200
    assert persisted.json()["show_hidden_enabled"] is True
