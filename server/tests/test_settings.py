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


def test_ai_settings_are_seeded(client: TestClient, auth_headers: dict[str, str]) -> None:
    """默认系统配置包含 AI 模型配置入口。"""

    response = client.get("/api/v1/settings", headers=auth_headers)
    assert response.status_code == 200
    settings = {item["setting_key"]: item for item in response.json()}

    assert settings["ai.feature_enabled"]["setting_value"] is False
    assert settings["ai.providers"]["setting_value"] == []
    assert settings["ai.providers"]["value_type"] == "json"
    assert settings["ai.active_provider_id"]["setting_value"] is None


def test_ai_provider_api_key_is_masked_and_preserved(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """AI 配置保存后不回显完整密钥，空密钥更新不会覆盖旧值。"""

    providers = [
        {
            "id": "openai-main",
            "name": "OpenAI 主模型",
            "provider_type": "openai_compatible",
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-secret-value",
            "model_name": "gpt-4.1",
            "enabled": True,
        },
        {
            "id": "ollama-local",
            "name": "Ollama 本地",
            "provider_type": "ollama",
            "base_url": "http://localhost:11434/v1",
            "api_key": "",
            "model_name": "llama3.1",
            "enabled": True,
        },
    ]

    create_response = client.put(
        "/api/v1/settings/ai.providers",
        headers=auth_headers,
        json={
            "setting_value": providers,
            "value_type": "json",
            "group_name": "ai",
            "is_public": False,
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()["setting_value"]
    assert created[0]["api_key"] is None
    assert created[0]["api_key_configured"] is True
    assert created[1]["api_key_configured"] is False

    update_response = client.put(
        "/api/v1/settings/ai.providers",
        headers=auth_headers,
        json={
            "setting_value": [
                {
                    **providers[0],
                    "api_key": "",
                    "model_name": "gpt-4.1-mini",
                }
            ],
            "value_type": "json",
            "group_name": "ai",
            "is_public": False,
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()["setting_value"]
    assert updated[0]["model_name"] == "gpt-4.1-mini"
    assert updated[0]["api_key"] is None
    assert updated[0]["api_key_configured"] is True


def test_deleted_active_ai_provider_is_repaired(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """删除当前默认模型后，默认模型自动切换到第一个启用配置。"""

    providers = [
        {
            "id": "first",
            "name": "First",
            "provider_type": "openai_compatible",
            "base_url": "https://api.example.com/v1",
            "api_key": "secret",
            "model_name": "first-model",
            "enabled": True,
        },
        {
            "id": "second",
            "name": "Second",
            "provider_type": "custom",
            "base_url": "https://api.example.com/v1",
            "api_key": "",
            "model_name": "second-model",
            "enabled": True,
        },
    ]
    client.put(
        "/api/v1/settings/ai.providers",
        headers=auth_headers,
        json={"setting_value": providers, "value_type": "json", "group_name": "ai"},
    )
    active_response = client.put(
        "/api/v1/settings/ai.active_provider_id",
        headers=auth_headers,
        json={"setting_value": "second"},
    )
    assert active_response.status_code == 200
    assert active_response.json()["setting_value"] == "second"

    delete_response = client.put(
        "/api/v1/settings/ai.providers",
        headers=auth_headers,
        json={
            "setting_value": [
                {
                    **providers[0],
                    "api_key": "",
                }
            ],
            "value_type": "json",
            "group_name": "ai",
        },
    )
    assert delete_response.status_code == 200

    settings_response = client.get("/api/v1/settings", headers=auth_headers)
    settings = {item["setting_key"]: item["setting_value"] for item in settings_response.json()}
    assert settings["ai.active_provider_id"] == "first"
