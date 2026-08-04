from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import reset_database_state
from app.main import create_app
from app.services.auth_service import AuthService


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """为每个测试创建独立 SQLite 和 storage，避免测试之间互相污染。"""

    db_path = tmp_path / "pfmt.sqlite3"
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    monkeypatch.setenv("PFMT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("PFMT_STORAGE_ROOT", storage_root.as_posix())
    monkeypatch.setenv("PFMT_JWT_SECRET_KEY", "test-jwt-secret-with-at-least-32-bytes")
    monkeypatch.setenv("PFMT_FILE_MASTER_KEY", "test-file-master-key")
    monkeypatch.setenv("PFMT_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("PFMT_ADMIN_PASSWORD", "admin123456")

    get_settings.cache_clear()
    reset_database_state()
    AuthService._failed_login_attempts.clear()
    AuthService._login_locks.clear()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    reset_database_state()
    get_settings.cache_clear()
    AuthService._failed_login_attempts.clear()
    AuthService._login_locks.clear()


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    """登录默认管理员并返回 Authorization 请求头。"""

    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123456"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
