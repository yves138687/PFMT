from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_client_ip, get_current_user, get_db_session
from app.core.config import Settings, get_settings
from app.models.user import UserAccount
from app.schemas.file import FileTagCreateRequest, FileTagItem
from app.services.file_service import FileService


router = APIRouter()


@router.get("", response_model=list[FileTagItem])
def list_tags(
    _current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> list[FileTagItem]:
    """读取全部活动标签。"""

    return FileService(db, settings).list_tags()


@router.post("", response_model=FileTagItem, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: FileTagCreateRequest,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> FileTagItem:
    """创建或复用标签。"""

    return FileService(db, settings).create_tag(
        payload=payload,
        current_user=current_user,
        client_ip=client_ip,
    )
