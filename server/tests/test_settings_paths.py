from fastapi.testclient import TestClient


def test_settings_can_be_read_and_updated(client: TestClient, auth_headers: dict[str, str]) -> None:
    """系统配置可读取、可更新并持久化。"""

    settings = client.get("/api/settings", headers=auth_headers)
    assert settings.status_code == 200
    keys = {item["setting_key"] for item in settings.json()}
    assert "storage.encryption_enabled" in keys
    assert "hidden.show_hidden_default" in keys

    update = client.put(
        "/api/settings/hidden.show_hidden_default",
        headers=auth_headers,
        json={"setting_value": True},
    )
    assert update.status_code == 200
    assert update.json()["setting_value"] is True


def test_path_tree_and_create_path(client: TestClient, auth_headers: dict[str, str]) -> None:
    """目录树包含根节点，并支持创建基础子目录。"""

    tree = client.get("/api/paths/tree", headers=auth_headers)
    assert tree.status_code == 200
    assert tree.json()[0]["path_id"] == "root"

    created = client.post(
        "/api/paths",
        headers=auth_headers,
        json={"parent_path_id": "root", "path_name": "阶段一资料", "path_type": "normal"},
    )
    assert created.status_code == 201
    assert created.json()["full_path"] == "/阶段一资料"

    tree_after = client.get("/api/paths/tree", headers=auth_headers)
    assert tree_after.status_code == 200
    root = tree_after.json()[0]
    assert any(child["path_name"] == "阶段一资料" for child in root["children"])
