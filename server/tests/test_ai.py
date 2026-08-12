from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.models.file import FileInfo


class FakeAiResponse:
    def __init__(self, answer: str = "AI result"):
        self.answer = answer

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"choices": [{"message": {"content": self.answer}}]}


class FakeAiClient:
    calls: list[dict[str, Any]] = []

    def __init__(self, timeout: float):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, Any]):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": self.timeout})
        return FakeAiResponse("Mocked summary")


def enable_ai_settings(client: TestClient, auth_headers: dict[str, str]) -> None:
    provider = {
        "id": "deepseek",
        "name": "DeepSeek",
        "provider_type": "openai_compatible",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "sk-deepseek",
        "model_name": "deepseek-chat",
        "enabled": True,
    }
    assert client.put(
        "/api/settings/ai.feature_enabled",
        headers=auth_headers,
        json={"setting_value": True, "value_type": "boolean", "group_name": "ai"},
    ).status_code == 200
    assert client.put(
        "/api/settings/ai.providers",
        headers=auth_headers,
        json={"setting_value": [provider], "value_type": "json", "group_name": "ai"},
    ).status_code == 200
    assert client.put(
        "/api/settings/ai.active_provider_id",
        headers=auth_headers,
        json={"setting_value": "deepseek", "value_type": "string", "group_name": "ai"},
    ).status_code == 200


def create_document(
    client: TestClient,
    auth_headers: dict[str, str],
    *,
    name: str = "doc.md",
    hidden: bool = False,
) -> str:
    response = client.post(
        "/api/files/document",
        headers=auth_headers,
        json={
            "path_id": "root",
            "original_name": name,
            "document_format": "markdown",
            "is_hidden": hidden,
        },
    )
    assert response.status_code == 201
    file_id = response.json()["file_id"]
    if hidden:
        return file_id
    save_response = client.put(
        f"/api/files/{file_id}/document",
        headers=auth_headers,
        json={"document_format": "markdown", "content": "# Title\nAI visible content"},
    )
    assert save_response.status_code == 200
    return file_id


def test_ai_feature_disabled_rejects_task(client: TestClient, auth_headers: dict[str, str]) -> None:
    file_id = create_document(client, auth_headers)

    response = client.post(
        "/api/ai/tasks",
        headers=auth_headers,
        json={"file_id": file_id, "task_type": "summary"},
    )

    assert response.status_code == 403


def test_ai_provider_must_be_configured(client: TestClient, auth_headers: dict[str, str]) -> None:
    file_id = create_document(client, auth_headers)
    assert client.put(
        "/api/settings/ai.feature_enabled",
        headers=auth_headers,
        json={"setting_value": True, "value_type": "boolean", "group_name": "ai"},
    ).status_code == 200

    response = client.post(
        "/api/ai/tasks",
        headers=auth_headers,
        json={"file_id": file_id, "task_type": "summary"},
    )

    assert response.status_code == 400
    assert "AI" in response.json()["message"]


def test_ai_task_calls_openai_compatible_provider(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    FakeAiClient.calls = []
    monkeypatch.setattr("app.services.ai_service.httpx.Client", FakeAiClient)
    enable_ai_settings(client, auth_headers)
    file_id = create_document(client, auth_headers)

    response = client.post(
        "/api/ai/tasks",
        headers=auth_headers,
        json={"file_id": file_id, "task_type": "summary"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task_status"] == "success"
    assert body["answer"] == "Mocked summary"
    assert FakeAiClient.calls
    call = FakeAiClient.calls[0]
    assert call["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer sk-deepseek"
    assert call["json"]["model"] == "deepseek-chat"
    assert "AI visible content" in call["json"]["messages"][1]["content"]


def test_ai_provider_verify_uses_unsaved_key(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    FakeAiClient.calls = []
    monkeypatch.setattr("app.services.ai_service.httpx.Client", FakeAiClient)

    response = client.post(
        "/api/settings/ai/providers/verify",
        headers=auth_headers,
        json={
            "id": "deepseek-draft",
            "name": "DeepSeek",
            "provider_type": "openai_compatible",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-unsaved",
            "model_name": "deepseek-chat",
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert FakeAiClient.calls[0]["headers"]["Authorization"] == "Bearer sk-unsaved"
    assert FakeAiClient.calls[0]["json"]["messages"][0]["content"].startswith("You are a connectivity checker")


def test_ai_provider_verify_can_reuse_saved_key(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    FakeAiClient.calls = []
    monkeypatch.setattr("app.services.ai_service.httpx.Client", FakeAiClient)
    enable_ai_settings(client, auth_headers)

    response = client.post(
        "/api/settings/ai/providers/verify",
        headers=auth_headers,
        json={
            "id": "deepseek",
            "name": "DeepSeek",
            "provider_type": "openai_compatible",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": None,
            "model_name": "deepseek-chat",
        },
    )

    assert response.status_code == 200
    assert FakeAiClient.calls[0]["headers"]["Authorization"] == "Bearer sk-deepseek"


def test_ai_provider_verify_accepts_full_chat_completions_url(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    FakeAiClient.calls = []
    monkeypatch.setattr("app.services.ai_service.httpx.Client", FakeAiClient)

    response = client.post(
        "/api/settings/ai/providers/verify",
        headers=auth_headers,
        json={
            "id": "deepseek-full-url",
            "name": "DeepSeek",
            "provider_type": "openai_compatible",
            "base_url": "https://api.deepseek.com/chat/completions",
            "api_key": "sk-unsaved",
            "model_name": "deepseek-chat",
        },
    )

    assert response.status_code == 200
    assert FakeAiClient.calls[0]["url"] == "https://api.deepseek.com/chat/completions"


def test_hidden_document_ai_respects_session_visibility(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    FakeAiClient.calls = []
    monkeypatch.setattr("app.services.ai_service.httpx.Client", FakeAiClient)
    enable_ai_settings(client, auth_headers)
    file_id = create_document(client, auth_headers, name="hidden.md", hidden=True)

    hidden_response = client.post(
        "/api/ai/tasks",
        headers=auth_headers,
        json={"file_id": file_id, "task_type": "summary"},
    )
    assert hidden_response.status_code == 404

    assert client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": True},
    ).status_code == 200
    visible_response = client.post(
        "/api/ai/tasks",
        headers=auth_headers,
        json={"file_id": file_id, "task_type": "summary"},
    )
    assert visible_response.status_code == 200
    assert '"includes_hidden_content":true' in visible_response.json()["read_scope"]


def test_ai_rejects_unsupported_file_type(client: TestClient, auth_headers: dict[str, str]) -> None:
    enable_ai_settings(client, auth_headers)
    response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        files={"file": ("image.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        data={"path_id": "root", "encryption_enabled": "true"},
    )
    assert response.status_code == 201
    file_id = response.json()["file_id"]

    ai_response = client.post(
        "/api/ai/tasks",
        headers=auth_headers,
        json={"file_id": file_id, "task_type": "summary"},
    )

    assert ai_response.status_code == 415


def test_summary_task_can_write_back_file_summary(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    FakeAiClient.calls = []
    monkeypatch.setattr("app.services.ai_service.httpx.Client", FakeAiClient)
    enable_ai_settings(client, auth_headers)
    file_id = create_document(client, auth_headers)
    task_response = client.post(
        "/api/ai/tasks",
        headers=auth_headers,
        json={"file_id": file_id, "task_type": "summary"},
    )
    assert task_response.status_code == 200

    write_response = client.post(
        f"/api/ai/tasks/{task_response.json()['task_id']}/write-summary",
        headers=auth_headers,
    )

    assert write_response.status_code == 200
    assert write_response.json()["summary_content"] == "Mocked summary"
    with Session(get_engine()) as db:
        file_info = db.query(FileInfo).filter(FileInfo.file_id == file_id).one()
        assert file_info.summary_source == "ai"
