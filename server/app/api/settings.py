from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_client_ip, get_current_user, get_db_session
from app.core.config import Settings, get_settings
from app.models.user import UserAccount
from app.schemas.setting import SettingItem, SettingUpdateRequest
from app.services.file_key_service import FileEncryptionStatus, FileKeyRotationService, FileKeyService
from app.services.setting_service import SettingService


router = APIRouter()


class FileEncryptionKeyRequest(BaseModel):
    key: str


class FileEncryptionStatusResponse(BaseModel):
    encryption_enabled: bool
    key_configured: bool
    active_key_id: str | None
    active_key_status: str | None
    pending_rotation_count: int


def _file_encryption_response(status: FileEncryptionStatus) -> FileEncryptionStatusResponse:
    return FileEncryptionStatusResponse(
        encryption_enabled=status.encryption_enabled,
        key_configured=status.key_configured,
        active_key_id=status.active_key_id,
        active_key_status=status.active_key_status,
        pending_rotation_count=status.pending_rotation_count,
    )


@router.get("/file-encryption", response_model=FileEncryptionStatusResponse)
def get_file_encryption_status(
    _current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> FileEncryptionStatusResponse:
    return _file_encryption_response(FileKeyService(db, settings).status())


@router.post("/file-encryption/enable", response_model=FileEncryptionStatusResponse)
def enable_file_encryption(
    payload: FileEncryptionKeyRequest,
    _current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> FileEncryptionStatusResponse:
    service = FileKeyService(db, settings)
    service.enable(payload.key)
    FileKeyRotationService(settings).start_once()
    return _file_encryption_response(service.status())


@router.post("/file-encryption/rotate", response_model=FileEncryptionStatusResponse)
def rotate_file_encryption_key(
    payload: FileEncryptionKeyRequest,
    _current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> FileEncryptionStatusResponse:
    service = FileKeyService(db, settings)
    service.rotate(payload.key)
    FileKeyRotationService(settings).start_once()
    return _file_encryption_response(service.status())


@router.post("/file-encryption/disable", response_model=FileEncryptionStatusResponse)
def disable_file_encryption_default(
    _current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> FileEncryptionStatusResponse:
    service = FileKeyService(db, settings)
    service.disable_default_encryption()
    return _file_encryption_response(service.status())


@router.get("", response_model=list[SettingItem])
def list_settings(
    _current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[SettingItem]:
    """读取系统配置列表，需要登录。"""

    return SettingService(db).list_settings()


@router.put("/{setting_key:path}", response_model=SettingItem)
def update_setting(
    setting_key: str,
    payload: SettingUpdateRequest,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    client_ip: str | None = Depends(get_client_ip),
) -> SettingItem:
    """写入单个系统配置，配置键允许包含点号。"""

    return SettingService(db).update_setting(
        setting_key=setting_key,
        payload=payload,
        updated_by=current_user.user_id,
        client_ip=client_ip,
    )
