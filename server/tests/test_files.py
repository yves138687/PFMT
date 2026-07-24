from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_engine
from app.models.audit import AuditLog
from app.models.file import FileInfo


def test_upload_uses_random_storage_object_name(client: TestClient, auth_headers: dict[str, str]) -> None:
    """上传文件必须使用随机 storage_object_name，不能复用原始文件名。"""

    payload = b"# Title\nsecret body\n"
    response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root"},
        files={"file": ("notes.md", payload, "text/markdown")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["original_name"] == "notes.md"
    assert body["storage_object_name"] != "notes.md"
    assert "notes" not in body["storage_object_name"].lower()
    assert body["encryption_enabled"] is True

    with Session(get_engine()) as db:
        file_info = db.execute(
            select(FileInfo).where(FileInfo.file_id == body["file_id"])
        ).scalar_one()
        object_path = get_settings().storage_root_path / Path(file_info.storage_path)
        stored_bytes = object_path.read_bytes()
        assert payload not in stored_bytes


def test_uploaded_markdown_can_be_read_after_decryption(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """加密上传后的 Markdown 可以通过读取接口解密返回。"""

    content = "# Doc\n\nhello markdown\n"
    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root"},
        files={"file": ("doc.markdown", content.encode("utf-8"), "text/markdown")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]

    read_response = client.get(f"/api/files/{file_id}/markdown", headers=auth_headers)

    assert read_response.status_code == 200
    assert read_response.json()["content"] == content
    with Session(get_engine()) as db:
        stmt = select(AuditLog).where(
            AuditLog.action_type == "read_markdown",
            AuditLog.action_result == "success",
            AuditLog.target_id == file_id,
        )
        assert db.execute(stmt).scalar_one_or_none() is not None


def test_uploaded_file_is_visible_in_folder_list(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """上传成功后，目录文件列表可以返回文件 ID、原始文件名和存储对象名。"""

    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root"},
        files={"file": ("folder-list.md", b"# Folder List\n", "text/markdown")},
    )
    assert upload_response.status_code == 201
    uploaded = upload_response.json()

    list_response = client.get("/api/files", headers=auth_headers, params={"path_id": "root"})

    assert list_response.status_code == 200
    files = list_response.json()
    assert len(files) == 1
    assert files[0]["file_id"] == uploaded["file_id"]
    assert files[0]["original_name"] == "folder-list.md"
    assert files[0]["storage_object_name"] == uploaded["storage_object_name"]
    assert files[0]["updated_at"]
