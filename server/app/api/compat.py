from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_bearer_token,
    get_client_ip,
    get_current_user,
    get_db_session,
)
from app.core.config import Settings, get_settings
from app.models.user import UserAccount
from app.repositories.setting_repository import SettingRepository
from app.schemas.auth import LoginRequest, TokenResponse, UserProfile
from app.schemas.file import FileUploadResponse, MarkdownReadResponse
from app.schemas.path import PathCreateRequest, PathRead
from app.schemas.setting import SettingUpdateRequest
from app.services.auth_service import AuthService
from app.services.file_service import FileService
from app.services.path_service import PathService
from app.services.setting_service import SettingService


router = APIRouter()


class CompatSettingUpdateItem(BaseModel):
    """兼容旧版批量配置更新请求。"""

    setting_key: str
    setting_value: Any


class CompatSettingUpdateRequest(BaseModel):
    """兼容旧版设置接口的 items 包裹结构。"""

    items: list[CompatSettingUpdateItem]


class CompatFlatSettingsRequest(BaseModel):
    """兼容合约里的扁平系统设置请求。"""

    file_encryption_enabled: bool | None = None
    hidden_feature_enabled: bool | None = None
    show_hidden_by_default: bool | None = None
    storage_root: str | None = None


class CompatPathCreateRequest(BaseModel):
    """兼容合约里的目录创建字段命名。"""

    parent_id: str = "root"
    name: str
    is_hidden: bool = False
    path_type: str = "normal"
    description: str | None = None


def _raw_settings(db: Session) -> dict[str, list[dict[str, Any]]]:
    """旧接口返回数据库原始字符串值，供早期联调脚本复用。"""

    repository = SettingRepository(db)
    return {
        "items": [
            {
                "setting_key": item.setting_key,
                "setting_value": item.setting_value,
                "value_type": item.value_type,
                "group_name": item.group_name,
                "description": item.description,
                "is_public": item.is_public,
                "updated_at": item.updated_at,
                "updated_by": item.updated_by,
            }
            for item in repository.list_all()
        ]
    }


def _flat_settings(db: Session) -> dict[str, Any]:
    """将内部配置键映射为早期合约里的扁平字段。"""

    repository = SettingRepository(db)

    def read_value(setting_key: str, default: Any) -> Any:
        item = repository.get_by_key(setting_key)
        if item is None:
            return default
        return SettingService.parse_value(item.setting_value, item.value_type)

    return {
        "file_encryption_enabled": read_value("storage.encryption_enabled", True),
        "hidden_feature_enabled": read_value("hidden.feature_enabled", True),
        "show_hidden_by_default": read_value("hidden.show_hidden_default", False),
        "storage_root": read_value("storage.local_root", "./storage"),
    }


def _compat_tree_node(node: Any) -> dict[str, Any]:
    """把新版目录树节点转换为早期合约中的 id/name 结构。"""

    return {
        "id": node.path_id,
        "path_id": node.path_id,
        "parent_id": node.parent_path_id,
        "parent_path_id": node.parent_path_id,
        "name": node.path_name,
        "path_name": node.path_name,
        "path_type": node.path_type,
        "full_path": node.full_path,
        "is_hidden": node.is_hidden,
        "children": [_compat_tree_node(child) for child in node.children],
    }


def _compat_path_read(path: PathRead) -> dict[str, Any]:
    """把新版目录响应补充为早期合约可识别字段。"""

    data = path.model_dump()
    data["id"] = path.path_id
    data["name"] = path.path_name
    data["parent_id"] = path.parent_path_id
    return data


@router.post("/auth/login", response_model=TokenResponse)
def login_compat(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> TokenResponse:
    """兼容 /api/auth/login 旧路径。"""

    return AuthService(db, settings).login(
        username=payload.username,
        password=payload.password,
        client_ip=client_ip,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/auth/me", response_model=UserProfile)
def me_compat(current_user: UserAccount = Depends(get_current_user)) -> UserProfile:
    """兼容 /api/auth/me 旧路径。"""

    return AuthService._to_profile(current_user)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_compat(
    token: str = Depends(get_bearer_token),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> None:
    """兼容 /api/auth/logout 旧路径。"""

    AuthService(db, settings).logout(token=token, current_user=current_user, client_ip=client_ip)


@router.get("/settings")
def list_settings_compat(
    _current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict[str, list[dict[str, Any]]]:
    """兼容 /api/settings 旧路径，正式接口为 /api/v1/settings。"""

    return _raw_settings(db)


@router.get("/system/settings")
def get_system_settings_compat(
    _current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """兼容 /api/system/settings 扁平读取接口。"""

    return _flat_settings(db)


@router.put("/system/settings")
def update_system_settings_compat(
    payload: CompatFlatSettingsRequest,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    client_ip: str | None = Depends(get_client_ip),
) -> dict[str, Any]:
    """兼容 /api/system/settings 扁平更新接口。"""

    service = SettingService(db)
    key_map = {
        "file_encryption_enabled": "storage.encryption_enabled",
        "hidden_feature_enabled": "hidden.feature_enabled",
        "show_hidden_by_default": "hidden.show_hidden_default",
        "storage_root": "storage.local_root",
    }
    for field_name, setting_key in key_map.items():
        value = getattr(payload, field_name)
        if value is None:
            continue
        service.update_setting(
            setting_key=setting_key,
            payload=SettingUpdateRequest(setting_value=value),
            updated_by=current_user.user_id,
            client_ip=client_ip,
        )
    return _flat_settings(db)


@router.put("/settings")
def update_settings_compat(
    payload: CompatSettingUpdateRequest,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    client_ip: str | None = Depends(get_client_ip),
) -> dict[str, list[dict[str, Any]]]:
    """兼容旧版批量更新配置接口。"""

    service = SettingService(db)
    for item in payload.items:
        service.update_setting(
            setting_key=item.setting_key,
            payload=SettingUpdateRequest(setting_value=item.setting_value),
            updated_by=current_user.user_id,
            client_ip=client_ip,
        )
    return _raw_settings(db)


@router.get("/paths/tree")
def get_path_tree_compat(
    show_hidden: bool | None = None,
    _current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """兼容 /api/paths/tree 旧响应包裹结构。"""

    return {"nodes": PathService(db).get_tree(show_hidden=show_hidden)}


@router.post("/paths", response_model=PathRead)
def create_path_compat(
    payload: PathCreateRequest,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    client_ip: str | None = Depends(get_client_ip),
) -> PathRead:
    """兼容 /api/paths 旧创建目录接口。"""

    return PathService(db).create_path(
        payload=payload,
        user_id=current_user.user_id,
        client_ip=client_ip,
    )


@router.get("/files/tree")
def get_file_tree_compat(
    show_hidden: bool | None = None,
    _current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """兼容 /api/files/tree 旧文件树接口。"""

    nodes = PathService(db).get_tree(show_hidden=show_hidden)
    return {"nodes": [_compat_tree_node(node) for node in nodes]}


@router.post("/files/paths")
def create_file_path_compat(
    payload: CompatPathCreateRequest,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    client_ip: str | None = Depends(get_client_ip),
) -> dict[str, Any]:
    """兼容 /api/files/paths 旧目录创建接口。"""

    created = PathService(db).create_path(
        payload=PathCreateRequest(
            parent_path_id=payload.parent_id,
            path_name=payload.name,
            path_type=payload.path_type,  # type: ignore[arg-type]
            is_hidden=payload.is_hidden,
            description=payload.description,
        ),
        user_id=current_user.user_id,
        client_ip=client_ip,
    )
    return _compat_path_read(created)


@router.post("/files/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file_compat(
    file: UploadFile = File(...),
    path_id: str = Form(default="root"),
    encrypt: bool | None = Form(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> FileUploadResponse:
    """兼容 /api/files/upload 旧上传接口，encrypt 映射为 encryption_enabled。"""

    return await FileService(db, settings).upload_file(
        upload_file=file,
        path_id=path_id,
        current_user=current_user,
        client_ip=client_ip,
        encryption_enabled=encrypt,
        is_hidden=False,
    )


@router.get("/files/{file_id}/markdown", response_model=MarkdownReadResponse)
def read_markdown_compat(
    file_id: str,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> MarkdownReadResponse:
    """兼容 /api/files/{file_id}/markdown 旧读取接口。"""

    return FileService(db, settings).read_markdown(
        file_id=file_id,
        show_hidden=None,
        current_user=current_user,
        client_ip=client_ip,
    )
