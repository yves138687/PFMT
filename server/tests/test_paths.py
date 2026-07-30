from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_engine
from app.models.file import FileInfo, FilePath


def test_path_tree_and_create_path(client: TestClient, auth_headers: dict[str, str]) -> None:
    """目录树默认包含 root，并支持创建子目录。"""

    tree_response = client.get("/api/v1/paths/tree", headers=auth_headers)
    assert tree_response.status_code == 200
    assert tree_response.json()[0]["path_id"] == "root"

    create_response = client.post(
        "/api/v1/paths",
        headers=auth_headers,
        json={"path_name": "Notes", "parent_path_id": "root"},
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["path_name"] == "Notes"
    assert created["full_path"] == "/Notes"
    assert "path_type" not in created

    tree_response = client.get("/api/v1/paths/tree", headers=auth_headers)
    root = tree_response.json()[0]
    assert [child["path_name"] for child in root["children"]] == ["Notes"]


def test_hidden_path_requires_session_switch(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """隐藏目录不受默认显示配置和查询参数影响，只由当前会话开关决定。"""

    update = client.put(
        "/api/settings/hidden.show_hidden_default",
        headers=auth_headers,
        json={"setting_value": True},
    )
    assert update.status_code == 200

    created = client.post(
        "/api/v1/paths",
        headers=auth_headers,
        json={
            "path_name": "Hidden Notes",
            "parent_path_id": "root",
            "path_type": "private",
            "is_hidden": True,
        },
    )
    assert created.status_code == 201

    tree = client.get("/api/v1/paths/tree", headers=auth_headers)
    root = tree.json()[0]
    assert "Hidden Notes" not in [child["path_name"] for child in root["children"]]

    visible_tree = client.get(
        "/api/v1/paths/tree",
        headers=auth_headers,
        params={"show_hidden": "true"},
    )
    visible_root = visible_tree.json()[0]
    assert "Hidden Notes" not in [child["path_name"] for child in visible_root["children"]]

    session_response = client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": True},
    )
    assert session_response.status_code == 200

    visible_tree = client.get(
        "/api/v1/paths/tree",
        headers=auth_headers,
    )
    visible_root = visible_tree.json()[0]
    hidden_node = next(child for child in visible_root["children"] if child["path_name"] == "Hidden Notes")
    assert "path_type" not in hidden_node
    with Session(get_engine()) as db:
        hidden_path = db.execute(select(FilePath).where(FilePath.path_id == hidden_node["path_id"])).scalar_one()
        assert hidden_path.path_type == "normal"


def test_path_can_be_moved_with_descendants(client: TestClient, auth_headers: dict[str, str]) -> None:
    """目录移动会同步更新目录本身和子目录的完整路径。"""

    source = client.post(
        "/api/v1/paths",
        headers=auth_headers,
        json={"path_name": "Source", "parent_path_id": "root"},
    ).json()
    target = client.post(
        "/api/v1/paths",
        headers=auth_headers,
        json={"path_name": "Target", "parent_path_id": "root"},
    ).json()
    child = client.post(
        "/api/v1/paths",
        headers=auth_headers,
        json={"path_name": "Child", "parent_path_id": source["path_id"]},
    ).json()

    move_response = client.patch(
        f"/api/v1/paths/{source['path_id']}/move",
        headers=auth_headers,
        json={"parent_path_id": target["path_id"]},
    )

    assert move_response.status_code == 200
    moved = move_response.json()
    assert moved["parent_path_id"] == target["path_id"]
    assert moved["full_path"] == "/Target/Source"

    with Session(get_engine()) as db:
        child_path = db.execute(
            select(FilePath).where(FilePath.path_id == child["path_id"])
        ).scalar_one()
        assert child_path.full_path == "/Target/Source/Child"
        assert child_path.path_level == 3


def test_path_can_be_renamed_and_hidden_with_descendants(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """目录重命名会同步子目录路径，隐藏目录默认不出现在目录树。"""

    parent = client.post(
        "/api/v1/paths",
        headers=auth_headers,
        json={"path_name": "Projects", "parent_path_id": "root"},
    ).json()
    child = client.post(
        "/api/v1/paths",
        headers=auth_headers,
        json={"path_name": "Alpha", "parent_path_id": parent["path_id"]},
    ).json()

    update_response = client.patch(
        f"/api/v1/paths/{parent['path_id']}",
        headers=auth_headers,
        json={"path_name": "Archive", "description": "done", "is_hidden": True},
    )

    assert update_response.status_code == 200
    assert update_response.json()["full_path"] == "/Archive"
    assert update_response.json()["is_hidden"] is True

    tree = client.get("/api/v1/paths/tree", headers=auth_headers).json()[0]
    assert "Archive" not in [item["path_name"] for item in tree["children"]]

    visible_tree = client.get(
        "/api/v1/paths/tree",
        headers=auth_headers,
        params={"show_hidden": "true"},
    ).json()[0]
    assert "Archive" not in [item["path_name"] for item in visible_tree["children"]]

    session_response = client.put(
        "/api/auth/hidden-content",
        headers=auth_headers,
        json={"enabled": True},
    )
    assert session_response.status_code == 200

    visible_tree = client.get(
        "/api/v1/paths/tree",
        headers=auth_headers,
    ).json()[0]
    assert "Archive" in [item["path_name"] for item in visible_tree["children"]]

    with Session(get_engine()) as db:
        child_path = db.execute(select(FilePath).where(FilePath.path_id == child["path_id"])).scalar_one()
        assert child_path.full_path == "/Archive/Alpha"


def test_path_delete_removes_subtree_files_and_frees_name(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """删除目录会级联删除子目录和文件，并允许重新创建同名目录。"""

    parent = client.post(
        "/api/v1/paths",
        headers=auth_headers,
        json={"path_name": "Trash", "parent_path_id": "root"},
    ).json()
    child = client.post(
        "/api/v1/paths",
        headers=auth_headers,
        json={"path_name": "Child", "parent_path_id": parent["path_id"]},
    ).json()
    upload_response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"path_id": child["path_id"]},
        files={"file": ("nested.md", b"# Nested\n", "text/markdown")},
    )
    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]

    with Session(get_engine()) as db:
        file_info = db.execute(select(FileInfo).where(FileInfo.file_id == file_id)).scalar_one()
        object_path = get_settings().storage_root_path / file_info.storage_path
        assert object_path.exists()

    delete_response = client.delete(f"/api/v1/paths/{parent['path_id']}", headers=auth_headers)
    assert delete_response.status_code == 204
    assert client.get("/api/files", headers=auth_headers, params={"path_id": child["path_id"]}).status_code == 404
    assert client.get(f"/api/files/{file_id}", headers=auth_headers).status_code == 404
    assert not object_path.exists()

    recreate_response = client.post(
        "/api/v1/paths",
        headers=auth_headers,
        json={"path_name": "Trash", "parent_path_id": "root"},
    )
    assert recreate_response.status_code == 201
    assert recreate_response.json()["full_path"] == "/Trash"

    with Session(get_engine()) as db:
        deleted_parent = db.execute(
            select(FilePath).where(FilePath.path_id == parent["path_id"])
        ).scalar_one()
        deleted_file = db.execute(select(FileInfo).where(FileInfo.file_id == file_id)).scalar_one()
        assert deleted_parent.status == "deleted"
        assert deleted_file.status == "deleted"
