from fastapi.testclient import TestClient


def test_business_api_requires_authentication(client: TestClient) -> None:
    """配置、目录和上传接口都必须先登录。"""

    assert client.get("/api/v1/settings").status_code == 401
    assert client.get("/api/v1/paths/tree").status_code == 401
    upload_response = client.post(
        "/api/v1/files/upload",
        data={"path_id": "root"},
        files={"file": ("notes.md", b"# Private\n", "text/markdown")},
    )
    assert upload_response.status_code == 401
