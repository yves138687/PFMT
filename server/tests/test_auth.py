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
