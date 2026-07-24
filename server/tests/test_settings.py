from fastapi.testclient import TestClient


def test_settings_can_be_read_and_updated(client: TestClient, auth_headers: dict[str, str]) -> None:
    """系统配置支持登录后读取和持久化更新。"""

    list_response = client.get("/api/v1/settings", headers=auth_headers)
    assert list_response.status_code == 200
    keys = {item["setting_key"] for item in list_response.json()}
    assert "storage.encryption_enabled" in keys
    assert "storage.local_root" in keys

    update_response = client.put(
        "/api/v1/settings/storage.encryption_enabled",
        headers=auth_headers,
        json={"setting_value": False},
    )
    assert update_response.status_code == 200
    assert update_response.json()["setting_value"] is False

    list_response = client.get("/api/v1/settings", headers=auth_headers)
    updated = {
        item["setting_key"]: item["setting_value"]
        for item in list_response.json()
    }
    assert updated["storage.encryption_enabled"] is False
