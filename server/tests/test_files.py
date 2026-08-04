from pathlib import Path
from datetime import timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import now_utc
from app.core.config import get_settings
from app.core.database import get_engine
from app.models.audit import AuditLog
from app.models.file import FileInfo, FileTag, FileTagRel
from app.services.storage_integrity_service import StorageIntegrityService
from app.services.storage_service import WINDOWS_MAX_COMPONENT_CHARS, WINDOWS_SAFE_MAX_PATH_CHARS


def test_upload_uses_random_storage_object_name(client: TestClient, auth_headers: dict[str, str]) -> None:
    """上传文件必须使用随机 storage_object_name，但响应不暴露底层对象名。"""

    payload = b"# Title\nsecret body\n"
    original_name = f"{'long-name-' * 18}.md"
    response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root"},
        files={"file": (original_name, payload, "text/markdown")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["original_name"] == original_name
    assert "storage_object_name" not in body
    assert "visibility_type" not in body
    assert body["encryption_enabled"] is True

    with Session(get_engine()) as db:
        file_info = db.execute(
            select(FileInfo).where(FileInfo.file_id == body["file_id"])
        ).scalar_one()
        assert file_info.storage_object_name != original_name
        assert "long-name" not in file_info.storage_object_name.lower()
        assert file_info.storage_path.startswith("data/")
        assert len(Path(file_info.storage_path).name) <= WINDOWS_MAX_COMPONENT_CHARS
        object_path = get_settings().storage_root_path / Path(file_info.storage_path)
        assert len(str(object_path)) <= WINDOWS_SAFE_MAX_PATH_CHARS
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
    assert "visibility_type" not in files[0]
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
    assert "visibility_type" not in detail


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


def test_file_metadata_rename_hidden_summary_tags_and_search(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """文件元数据更新、标签绑定和搜索都遵守隐藏过滤。"""

    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root"},
        files={"file": ("draft.md", b"# Draft\n", "text/markdown")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]

    update_response = client.patch(
        f"/api/files/{file_id}",
        headers=auth_headers,
        json={
            "original_name": "renamed.md",
            "remark": "project alpha",
            "summary_content": "manual summary",
            "is_hidden": True,
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["original_name"] == "renamed.md"
    assert updated["logical_path"] == "/renamed.md"
    assert updated["summary_content"] == "manual summary"
    assert updated["is_hidden"] is True

    hidden_search = client.get("/api/files/search", headers=auth_headers, params={"q": "alpha"})
    assert hidden_search.status_code == 200
    assert hidden_search.json()["items"] == []

    unauthorized_visible_search = client.get(
        "/api/files/search",
        headers=auth_headers,
        params={"q": "alpha", "show_hidden": "true"},
    )
    assert unauthorized_visible_search.status_code == 200
    assert unauthorized_visible_search.json()["items"] == []

    session_response = client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": True},
    )
    assert session_response.status_code == 200

    tags_response = client.put(
        f"/api/files/{file_id}/tags",
        headers=auth_headers,
        json={"tag_names": ["work", "alpha", "work"]},
    )
    assert tags_response.status_code == 200
    assert [tag["tag_name"] for tag in tags_response.json()["tags"]] == ["alpha", "work"]

    visible_search = client.get(
        "/api/files/search",
        headers=auth_headers,
        params={"q": "alpha"},
    )
    assert visible_search.status_code == 200
    items = visible_search.json()["items"]
    assert len(items) == 1
    assert items[0]["file_id"] == file_id
    assert items[0]["is_hidden"] is True
    assert "visibility_type" not in items[0]

    with Session(get_engine()) as db:
        file_info = db.execute(select(FileInfo).where(FileInfo.file_id == file_id)).scalar_one()
        assert file_info.original_name == "renamed.md"
        assert file_info.summary_source == "manual"
        assert db.execute(select(FileTag).where(FileTag.tag_name == "alpha")).scalar_one_or_none() is not None
        assert len(db.execute(select(FileTagRel).where(FileTagRel.file_id == file_id)).scalars().all()) == 2


def test_image_preview_stream_decrypts_uploaded_content(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """图片预览接口返回解密后的文件内容。"""

    payload = b"\x89PNG\r\n\x1a\nfake-image"
    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root"},
        files={"file": ("image.png", payload, "image/png")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]

    preview_response = client.get(f"/api/files/{file_id}/preview", headers=auth_headers)

    assert preview_response.status_code == 200
    assert preview_response.headers["content-type"].startswith("image/png")
    assert preview_response.content == payload


def test_unencrypted_video_stream_supports_http_range(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """未加密视频按 HTTP Range 返回浏览器可拖动播放所需的 206 响应。"""

    payload = b"0123456789" * 30
    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root", "encryption_enabled": "false"},
        files={"file": ("clip.mp4", payload, "video/mp4")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]

    token_response = client.post(f"/api/files/{file_id}/preview-token", headers=auth_headers)
    assert token_response.status_code == 200
    preview_url = token_response.json()["preview_url"]

    stream_response = client.get(preview_url, headers={"Range": "bytes=10-109"})

    assert stream_response.status_code == 206
    assert stream_response.headers["accept-ranges"] == "bytes"
    assert stream_response.headers["content-range"] == f"bytes 10-109/{len(payload)}"
    assert stream_response.headers["content-length"] == "100"
    assert stream_response.headers["content-type"].startswith("video/mp4")
    assert stream_response.content == payload[10:110]


def test_encrypted_video_stream_supports_cross_chunk_range(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """加密视频 Range 跨越多个加密分块时仍返回正确明文片段。"""

    chunk_size = get_settings().upload_chunk_size
    payload = bytes((index % 251 for index in range(chunk_size + 512)))
    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root", "encryption_enabled": "true"},
        files={"file": ("encrypted.mp4", payload, "video/mp4")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]

    token_response = client.post(f"/api/files/{file_id}/preview-token", headers=auth_headers)
    assert token_response.status_code == 200
    preview_url = token_response.json()["preview_url"]
    start = chunk_size - 64
    end = chunk_size + 127

    stream_response = client.get(preview_url, headers={"Range": f"bytes={start}-{end}"})

    assert stream_response.status_code == 206
    assert stream_response.headers["content-range"] == f"bytes {start}-{end}/{len(payload)}"
    assert stream_response.content == payload[start : end + 1]


def test_video_stream_token_validation_and_type_checks(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """视频流只接受短时效视频预览 Token，且拒绝非视频文件。"""

    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root"},
        files={"file": ("note.txt", b"plain", "text/plain")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]

    assert client.post(f"/api/files/{file_id}/preview-token", headers=auth_headers).status_code == 415
    assert client.get(f"/api/files/{file_id}/video-stream").status_code == 401

    expired = now_utc() - timedelta(minutes=1)
    expired_token = jwt.encode(
        {
            "sub": "user_admin",
            "fid": file_id,
            "purpose": "video_preview",
            "exp": expired.replace(tzinfo=timezone.utc),
        },
        get_settings().effective_jwt_secret,
        algorithm=get_settings().jwt_algorithm,
    )
    assert client.get(f"/api/files/{file_id}/video-stream", params={"token": expired_token}).status_code == 401

    wrong_purpose_token = jwt.encode(
        {
            "sub": "user_admin",
            "fid": file_id,
            "purpose": "image_preview",
            "exp": (now_utc() + timedelta(minutes=5)).replace(tzinfo=timezone.utc),
        },
        get_settings().effective_jwt_secret,
        algorithm=get_settings().jwt_algorithm,
    )
    assert client.get(f"/api/files/{file_id}/video-stream", params={"token": wrong_purpose_token}).status_code == 401


def test_hidden_video_preview_token_respects_visibility_flag(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """隐藏视频默认不能签发播放 Token，显式显示隐藏内容后才可播放。"""

    payload = b"hidden-video"
    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root", "is_hidden": "true"},
        files={"file": ("hidden.mp4", payload, "video/mp4")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]

    hidden_token_response = client.post(f"/api/files/{file_id}/preview-token", headers=auth_headers)
    assert hidden_token_response.status_code == 404

    unauthorized_token_response = client.post(
        f"/api/files/{file_id}/preview-token",
        headers=auth_headers,
        params={"show_hidden": "true"},
    )
    assert unauthorized_token_response.status_code == 404

    session_response = client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": True},
    )
    assert session_response.status_code == 200

    visible_token_response = client.post(
        f"/api/files/{file_id}/preview-token",
        headers=auth_headers,
    )
    assert visible_token_response.status_code == 200
    stream_response = client.get(visible_token_response.json()["preview_url"], headers={"Range": "bytes=0-5"})
    assert stream_response.status_code == 206
    assert stream_response.content == payload[:6]


def test_file_can_be_moved_and_deleted(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """文件支持移动目录和删除，删除后不再暴露详情并清理对象。"""

    path_response = client.post(
        "/api/paths",
        headers=auth_headers,
        json={"path_name": "Archive", "parent_path_id": "root"},
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
    with Session(get_engine()) as db:
        moved_file_info = db.execute(select(FileInfo).where(FileInfo.file_id == file_id)).scalar_one()
        moved_object_path = get_settings().storage_root_path / Path(moved_file_info.storage_path)
        assert moved_object_path.exists()
        assert not object_path.exists()

    delete_response = client.delete(f"/api/files/{file_id}", headers=auth_headers)
    assert delete_response.status_code == 204
    assert client.get(f"/api/files/{file_id}", headers=auth_headers).status_code == 404
    assert not moved_object_path.exists()

    with Session(get_engine()) as db:
        file_info = db.execute(select(FileInfo).where(FileInfo.file_id == file_id)).scalar_one()
        assert file_info.status == "deleted"
        stmt = select(AuditLog).where(
            AuditLog.action_type == "delete_file",
            AuditLog.action_result == "success",
            AuditLog.target_id == file_id,
        )
        assert db.execute(stmt).scalar_one_or_none() is not None


def test_storage_inventory_warns_when_active_file_is_missing(
    client: TestClient,
    auth_headers: dict[str, str],
    caplog,
) -> None:
    """SQLite 清单内个别文件缺失只记录告警，不阻断校验。"""

    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root"},
        files={"file": ("missing.md", b"# Missing\n", "text/markdown")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]
    with Session(get_engine()) as db:
        file_info = db.execute(select(FileInfo).where(FileInfo.file_id == file_id)).scalar_one()
        object_path = get_settings().storage_root_path / Path(file_info.storage_path)
    object_path.unlink()

    caplog.set_level("WARNING", logger="pfmt.storage")
    StorageIntegrityService(get_settings()).verify_inventory()

    assert "SQLite 清单中的文件缺失真实存储对象" in caplog.text


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

    unauthorized_detail = client.get(
        f"/api/files/{file_id}",
        headers=auth_headers,
        params={"show_hidden": "true"},
    )
    assert unauthorized_detail.status_code == 404

    session_response = client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": True},
    )
    assert session_response.status_code == 200

    visible_detail = client.get(
        f"/api/files/{file_id}",
        headers=auth_headers,
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


def test_plain_text_file_can_be_read_after_decryption(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """普通文本文件可以进入只读查看接口，Markdown 专用接口仍保持收窄。"""

    content = "第一行\nplain text\n"
    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root", "encryption_enabled": "true"},
        files={"file": ("note.txt", content.encode("utf-8"), "text/plain")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]

    markdown_response = client.get(f"/api/files/{file_id}/markdown", headers=auth_headers)
    assert markdown_response.status_code == 415

    text_response = client.get(f"/api/files/{file_id}/text", headers=auth_headers)

    assert text_response.status_code == 200
    body = text_response.json()
    assert body["file_id"] == file_id
    assert body["original_name"] == "note.txt"
    assert body["content"] == content


def test_document_endpoint_reads_text_markdown_and_html(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """统一文档接口覆盖 txt、Markdown 和 HTML。"""

    cases = [
        ("note.txt", "plain text", "text/plain", "plain_text"),
        ("note.md", "# 标题\n正文", "text/markdown", "markdown"),
        ("note.html", "<h1>标题</h1><p>正文</p>", "text/html", "html"),
    ]

    for filename, content, mime_type, expected_format in cases:
        upload_response = client.post(
            "/api/files/upload",
            headers=auth_headers,
            data={"path_id": "root", "encryption_enabled": "true"},
            files={"file": (filename, content.encode("utf-8"), mime_type)},
        )
        assert upload_response.status_code == 201
        file_id = upload_response.json()["file_id"]

        document_response = client.get(f"/api/files/{file_id}/document", headers=auth_headers)

        assert document_response.status_code == 200
        body = document_response.json()
        assert body["file_id"] == file_id
        assert body["document_format"] == expected_format
        assert body["content"] == content
        assert body["editable"] is True
        assert body["rendered_html"]


def test_create_document_uses_encrypted_generated_file_pipeline(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """新建空白文档支持三种格式，并复用随机对象名和加密存储链路。"""

    cases = [
        ("plain_text", "scratch", "scratch.txt", ".txt", "text/plain"),
        ("markdown", "notes.txt", "notes.md", ".md", "text/markdown"),
        ("html", "page", "page.html", ".html", "text/html"),
    ]

    for document_format, requested_name, expected_name, expected_ext, expected_mime in cases:
        response = client.post(
            "/api/files/document",
            headers=auth_headers,
            json={
                "path_id": "root",
                "original_name": requested_name,
                "document_format": document_format,
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["original_name"] == expected_name
        assert body["file_ext"] == expected_ext
        assert body["mime_type"] == expected_mime
        assert body["file_type"] == "text"
        assert body["size_bytes"] == 0
        assert body["encryption_enabled"] is True
        assert body["is_hidden"] is False
        assert "storage_object_name" not in body
        assert "storage_path" not in body
        assert "visibility_type" not in body

        read_response = client.get(f"/api/files/{body['file_id']}/document", headers=auth_headers)
        assert read_response.status_code == 200
        assert read_response.json()["document_format"] == document_format
        assert read_response.json()["content"] == ""

        with Session(get_engine()) as db:
            file_info = db.execute(select(FileInfo).where(FileInfo.file_id == body["file_id"])).scalar_one()
            assert file_info.storage_object_name != expected_name
            assert file_info.visibility_type == "normal"
            object_path = get_settings().storage_root_path / Path(file_info.storage_path)
            assert object_path.exists()
            assert object_path.stat().st_size > 0


def test_create_hidden_document_respects_session_visibility(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """隐藏文档创建后默认不可见，开启当前会话隐藏展示后才可读取。"""

    response = client.post(
        "/api/files/document",
        headers=auth_headers,
        json={
            "path_id": "root",
            "original_name": "hidden.md",
            "document_format": "markdown",
            "is_hidden": True,
        },
    )
    assert response.status_code == 201
    file_id = response.json()["file_id"]

    list_response = client.get("/api/files", headers=auth_headers, params={"path_id": "root"})
    assert list_response.status_code == 200
    assert [item["file_id"] for item in list_response.json()] == []
    assert client.get(f"/api/files/{file_id}/document", headers=auth_headers).status_code == 404

    session_response = client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": True},
    )
    assert session_response.status_code == 200

    visible_list_response = client.get("/api/files", headers=auth_headers, params={"path_id": "root"})
    assert visible_list_response.status_code == 200
    visible_items = visible_list_response.json()
    assert [item["file_id"] for item in visible_items] == [file_id]
    assert visible_items[0]["is_hidden"] is True

    read_response = client.get(f"/api/files/{file_id}/document", headers=auth_headers)
    assert read_response.status_code == 200
    assert read_response.json()["content"] == ""


def test_document_save_updates_encrypted_content(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """保存统一文档会替换加密对象内容，并更新可读正文和文件大小。"""

    original = "before\n"
    updated = "after\n第二行"
    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root", "encryption_enabled": "true"},
        files={"file": ("editable.txt", original.encode("utf-8"), "text/plain")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]
    old_size = upload_response.json()["size_bytes"]

    save_response = client.put(
        f"/api/files/{file_id}/document",
        headers=auth_headers,
        json={"document_format": "plain_text", "content": updated},
    )

    assert save_response.status_code == 200
    body = save_response.json()
    assert body["content"] == updated
    assert body["size_bytes"] == len(updated.encode("utf-8"))
    assert body["size_bytes"] != old_size

    text_response = client.get(f"/api/files/{file_id}/text", headers=auth_headers)
    assert text_response.status_code == 200
    assert text_response.json()["content"] == updated


def test_hidden_file_cannot_bypass_visibility_through_document_endpoint(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """隐藏文件不能通过统一文档接口绕过会话态显示隐藏开关。"""

    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root", "is_hidden": "true"},
        files={"file": ("hidden.md", b"# hidden", "text/markdown")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]

    assert client.get(f"/api/files/{file_id}/document", headers=auth_headers).status_code == 404


def test_document_convert_creates_new_file_and_keeps_source(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """文档转换默认生成新文件，不覆盖源文件。"""

    content = "# Title\nBody"
    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root", "encryption_enabled": "true"},
        files={"file": ("source.md", content.encode("utf-8"), "text/markdown")},
    )
    assert upload_response.status_code == 201
    source_file_id = upload_response.json()["file_id"]

    convert_response = client.post(
        f"/api/files/{source_file_id}/convert",
        headers=auth_headers,
        json={"target_format": "html", "target_name": "source-copy.html"},
    )

    assert convert_response.status_code == 201
    converted = convert_response.json()
    assert converted["file_id"] != source_file_id
    assert converted["original_name"] == "source-copy.html"
    assert converted["file_ext"] == ".html"
    assert converted["mime_type"] == "text/html"

    source_document = client.get(f"/api/files/{source_file_id}/document", headers=auth_headers)
    converted_document = client.get(f"/api/files/{converted['file_id']}/document", headers=auth_headers)

    assert source_document.status_code == 200
    assert source_document.json()["content"] == content
    assert converted_document.status_code == 200
    assert converted_document.json()["document_format"] == "html"
    assert "<h1>Title</h1>" in converted_document.json()["content"]


def test_document_merge_creates_new_markdown_by_original_name_order(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """批量合并按原始文件名升序生成新 Markdown 文档，并保留源文件。"""

    first = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root", "encryption_enabled": "true"},
        files={"file": ("a.md", b"# A\none", "text/markdown")},
    )
    second = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root", "encryption_enabled": "true"},
        files={"file": ("b.txt", "two".encode("utf-8"), "text/plain")},
    )
    assert first.status_code == 201
    assert second.status_code == 201

    merge_response = client.post(
        "/api/files/merge",
        headers=auth_headers,
        json={
            "file_ids": [second.json()["file_id"], first.json()["file_id"]],
            "target_format": "markdown",
            "target_name": "merged.md",
        },
    )

    assert merge_response.status_code == 201
    merged = merge_response.json()
    assert merged["original_name"] == "merged.md"
    assert merged["file_ext"] == ".md"
    assert merged["mime_type"] == "text/markdown"

    merged_document = client.get(f"/api/files/{merged['file_id']}/document", headers=auth_headers)
    assert merged_document.status_code == 200
    content = merged_document.json()["content"]
    assert content.index("# a.md") < content.index("# b.txt")
    assert "two" in content
    assert "# A" in content

    assert client.get(f"/api/files/{first.json()['file_id']}/document", headers=auth_headers).json()["content"] == "# A\none"


def test_document_merge_rejects_non_document_file(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """非文档文件不能被批量合并。"""

    text_upload = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root"},
        files={"file": ("a.txt", b"one", "text/plain")},
    )
    image_upload = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root"},
        files={"file": ("image.png", b"not-a-real-png", "image/png")},
    )
    assert text_upload.status_code == 201
    assert image_upload.status_code == 201

    merge_response = client.post(
        "/api/files/merge",
        headers=auth_headers,
        json={"file_ids": [text_upload.json()["file_id"], image_upload.json()["file_id"]]},
    )

    assert merge_response.status_code == 415


def test_document_merge_respects_hidden_visibility(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """隐藏文档不能通过合并接口绕过会话态显示隐藏开关。"""

    visible = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root"},
        files={"file": ("visible.txt", b"visible", "text/plain")},
    )
    hidden = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root", "is_hidden": "true"},
        files={"file": ("hidden.txt", b"hidden", "text/plain")},
    )
    assert visible.status_code == 201
    assert hidden.status_code == 201

    merge_response = client.post(
        "/api/files/merge",
        headers=auth_headers,
        json={"file_ids": [visible.json()["file_id"], hidden.json()["file_id"]]},
    )

    assert merge_response.status_code == 404


def test_non_text_file_rejects_text_read(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """图片等非文本类型不能通过文本读取接口误读。"""

    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": "root"},
        files={"file": ("image.png", b"not-a-real-png", "image/png")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]

    read_response = client.get(f"/api/files/{file_id}/text", headers=auth_headers)

    assert read_response.status_code == 415
