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
    """上传成功后，目录文件列表返回用户侧元数据，不暴露存储对象名。"""

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
    assert "storage_object_name" not in files[0]
    assert "storage_path" not in files[0]
    assert files[0]["updated_at"]


def test_file_detail_returns_logical_path_without_storage_fields(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """文件详情返回业务逻辑路径，但不返回底层存储对象信息。"""

    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root"},
        files={"file": ("detail.md", b"# Detail\n", "text/markdown")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]

    detail_response = client.get(f"/api/files/{file_id}", headers=auth_headers)

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["file_id"] == file_id
    assert detail["logical_path"] == "/detail.md"
    assert detail["remark"] is None
    assert "storage_object_name" not in detail
    assert "storage_path" not in detail


def test_file_remark_can_be_saved_and_cleared(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """文件备注支持保存和清空，并写入文件元数据。"""

    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root"},
        files={"file": ("remark.md", b"# Remark\n", "text/markdown")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]

    save_response = client.patch(
        f"/api/files/{file_id}",
        headers=auth_headers,
        json={"remark": "第一行\n第二行"},
    )
    assert save_response.status_code == 200
    assert save_response.json()["remark"] == "第一行\n第二行"

    clear_response = client.patch(
        f"/api/files/{file_id}",
        headers=auth_headers,
        json={"remark": "   "},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["remark"] is None

    with Session(get_engine()) as db:
        file_info = db.execute(select(FileInfo).where(FileInfo.file_id == file_id)).scalar_one()
        assert file_info.remark is None
        stmt = select(AuditLog).where(
            AuditLog.action_type == "update_file_remark",
            AuditLog.action_result == "success",
            AuditLog.target_id == file_id,
        )
        assert db.execute(stmt).scalars().first() is not None


def test_file_can_be_moved_and_deleted(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """文件支持移动目录和删除，删除后不再暴露详情并清理对象。"""

    path_response = client.post(
        "/api/paths",
        headers=auth_headers,
        json={"path_name": "Archive", "parent_path_id": "root", "path_type": "normal"},
    )
    assert path_response.status_code == 201
    target_path_id = path_response.json()["path_id"]

    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root"},
        files={"file": ("movable.md", b"# Move\n", "text/markdown")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]

    with Session(get_engine()) as db:
        file_info = db.execute(select(FileInfo).where(FileInfo.file_id == file_id)).scalar_one()
        object_path = get_settings().storage_root_path / Path(file_info.storage_path)
        assert object_path.exists()

    move_response = client.patch(
        f"/api/files/{file_id}/move",
        headers=auth_headers,
        json={"path_id": target_path_id},
    )
    assert move_response.status_code == 200
    assert move_response.json()["path_id"] == target_path_id
    assert move_response.json()["logical_path"] == "/Archive/movable.md"

    assert client.get("/api/files", headers=auth_headers, params={"path_id": "root"}).json() == []
    moved_files = client.get(
        "/api/files",
        headers=auth_headers,
        params={"path_id": target_path_id},
    ).json()
    assert [item["file_id"] for item in moved_files] == [file_id]

    delete_response = client.delete(f"/api/files/{file_id}", headers=auth_headers)
    assert delete_response.status_code == 204
    assert client.get(f"/api/files/{file_id}", headers=auth_headers).status_code == 404
    assert not object_path.exists()

    with Session(get_engine()) as db:
        file_info = db.execute(select(FileInfo).where(FileInfo.file_id == file_id)).scalar_one()
        assert file_info.status == "deleted"
        stmt = select(AuditLog).where(
            AuditLog.action_type == "delete_file",
            AuditLog.action_result == "success",
            AuditLog.target_id == file_id,
        )
        assert db.execute(stmt).scalar_one_or_none() is not None


def test_hidden_file_detail_and_markdown_respect_visibility_flag(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """隐藏文件不能通过详情或 Markdown 读取接口绕过显示隐藏内容开关。"""

    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root", "is_hidden": "true"},
        files={"file": ("hidden.md", b"# Hidden\n", "text/markdown")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]

    assert client.get(f"/api/files/{file_id}", headers=auth_headers).status_code == 404
    assert client.get(f"/api/files/{file_id}/markdown", headers=auth_headers).status_code == 404

    visible_detail = client.get(
        f"/api/files/{file_id}",
        headers=auth_headers,
        params={"show_hidden": "true"},
    )
    assert visible_detail.status_code == 200
    assert visible_detail.json()["is_hidden"] is True


def test_non_markdown_file_still_rejects_markdown_read(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """非 Markdown 文件进入详情后，读取正文接口仍返回不支持。"""

    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root"},
        files={"file": ("image.png", b"not-a-real-png", "image/png")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]

    read_response = client.get(f"/api/files/{file_id}/markdown", headers=auth_headers)

    assert read_response.status_code == 415
