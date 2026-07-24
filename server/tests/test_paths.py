from fastapi.testclient import TestClient


def test_path_tree_and_create_path(client: TestClient, auth_headers: dict[str, str]) -> None:
    """目录树默认包含 root，并支持创建子目录。"""

    tree_response = client.get("/api/v1/paths/tree", headers=auth_headers)
    assert tree_response.status_code == 200
    assert tree_response.json()[0]["path_id"] == "root"

    create_response = client.post(
        "/api/v1/paths",
        headers=auth_headers,
        json={"path_name": "Notes", "parent_path_id": "root", "path_type": "normal"},
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["path_name"] == "Notes"
    assert created["full_path"] == "/Notes"

    tree_response = client.get("/api/v1/paths/tree", headers=auth_headers)
    root = tree_response.json()[0]
    assert [child["path_name"] for child in root["children"]] == ["Notes"]
