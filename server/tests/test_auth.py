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

    disabled = client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["show_hidden_enabled"] is False


def test_hidden_content_enable_requires_configured_second_password(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """配置二次验证码后，开启隐藏内容必须输入正确验证码。"""

    set_code = client.put(
        "/api/auth/hidden-content/password",
        headers=auth_headers,
        json={"new_password": "secret-6"},
    )
    assert set_code.status_code == 200
    assert set_code.json()["configured"] is True

    missing = client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": True},
    )
    assert missing.status_code == 403

    wrong = client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": True, "password": "wrong-xx"},
    )
    assert wrong.status_code == 403

    ok = client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": True, "password": "secret-6"},
    )
    assert ok.status_code == 200
    assert ok.json()["show_hidden_enabled"] is True


def test_hidden_content_password_change_requires_current_password(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """修改二次验证码必须先通过当前验证码校验。"""

    set_code = client.put(
        "/api/auth/hidden-content/password",
        headers=auth_headers,
        json={"new_password": "secret-6"},
    )
    assert set_code.status_code == 200

    wrong = client.put(
        "/api/auth/hidden-content/password",
        headers=auth_headers,
        json={"current_password": "wrong-xx", "new_password": "next-66"},
    )
    assert wrong.status_code == 403

    ok = client.put(
        "/api/auth/hidden-content/password",
        headers=auth_headers,
        json={"current_password": "secret-6", "new_password": "next-66"},
    )
    assert ok.status_code == 200
    assert ok.json()["configured"] is True

    with_old = client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": True, "password": "secret-6"},
    )
    assert with_old.status_code == 403

    with_new = client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": True, "password": "next-66"},
    )
    assert with_new.status_code == 200


def test_hidden_content_password_clearing_requires_current_password(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """清除二次验证码同样需要先通过当前验证码校验。"""

    set_code = client.put(
        "/api/auth/hidden-content/password",
        headers=auth_headers,
        json={"new_password": "secret-6"},
    )
    assert set_code.status_code == 200

    fail = client.put(
        "/api/auth/hidden-content/password",
        headers=auth_headers,
        json={"current_password": "wrong-xx", "new_password": ""},
    )
    assert fail.status_code == 403

    ok = client.put(
        "/api/auth/hidden-content/password",
        headers=auth_headers,
        json={"current_password": "secret-6", "new_password": ""},
    )
    assert ok.status_code == 200
    assert ok.json()["configured"] is False

    enable = client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": True},
    )
    assert enable.status_code == 200


def test_hidden_content_password_too_short_is_rejected(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """二次验证码长度不足 6 位时被拒绝。"""

    response = client.put(
        "/api/auth/hidden-content/password",
        headers=auth_headers,
        json={"new_password": "12345"},
    )
    assert response.status_code == 400
    assert "6 位" in response.json()["message"]


def test_hidden_content_force_switch_blocks_enable_without_code(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """开启“未配置时禁止开启”后，未配置验证码时不允许开启隐藏内容。"""

    update = client.put(
        "/api/settings/hidden.verify_password_required",
        headers=auth_headers,
        json={"setting_value": True},
    )
    assert update.status_code == 200
    assert update.json()["setting_value"] is True

    blocked = client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": True},
    )
    assert blocked.status_code == 403
    assert "验证码" in blocked.json()["message"]

    # 配置验证码后即可正常开启
    set_code = client.put(
        "/api/auth/hidden-content/password",
        headers=auth_headers,
        json={"new_password": "secret-6"},
    )
    assert set_code.status_code == 200

    ok = client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": True, "password": "secret-6"},
    )
    assert ok.status_code == 200


def test_hidden_content_password_hash_is_never_exposed(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """设置二次验证码后，设置接口只返回状态，绝不回显哈希原文。"""

    client.put(
        "/api/auth/hidden-content/password",
        headers=auth_headers,
        json={"new_password": "secret-6"},
    )

    settings = client.get("/api/settings", headers=auth_headers)
    assert settings.status_code == 200
    items = settings.json()
    hash_item = next(
        item for item in items if item["setting_key"] == "hidden.verify_password_hash"
    )
    assert hash_item["setting_value"] is True
    assert hash_item["value_type"] == "boolean"

    # 兼容批量写接口的返回值同样脱敏
    compat = client.put(
        "/api/settings",
        headers=auth_headers,
        json={"items": [{"setting_key": "hidden.show_hidden_default", "setting_value": False}]},
    )
    assert compat.status_code == 200
    compat_hash_item = next(
        item for item in compat.json()["items"] if item["setting_key"] == "hidden.verify_password_hash"
    )
    assert compat_hash_item["setting_value"] is True
    assert compat_hash_item["value_type"] == "boolean"


def test_hidden_content_password_cannot_be_written_via_generic_settings(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """隐藏内容二次验证码只能通过专用接口修改，通用配置接口拒绝写入。"""

    response = client.put(
        "/api/settings/hidden.verify_password_hash",
        headers=auth_headers,
        json={"setting_value": "secret-6"},
    )
    assert response.status_code == 403


def test_hidden_content_password_verification_rate_limit(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """二次验证码连续失败达到阈值后会被临时锁定。"""

    client.put(
        "/api/auth/hidden-content/password",
        headers=auth_headers,
        json={"new_password": "secret-6"},
    )

    for _index in range(5):
        response = client.put(
            "/api/auth/hidden-content",
            headers=auth_headers,
            json={"enabled": True, "password": "wrong-xx"},
        )
        assert response.status_code == 403

    locked = client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": True, "password": "secret-6"},
    )
    assert locked.status_code == 429
