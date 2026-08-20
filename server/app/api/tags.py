from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_client_ip, get_current_user, get_db_session
from app.core.config import Settings, get_settings
from app.models.user import UserAccount
from app.schemas.file import (
    FileSearchResponse,
    FileTagCreateRequest,
    FileTagImportRequest,
    FileTagImportResponse,
    FileTagItem,
    FileTagUpdateRequest,
)
from app.services.file_service import FileService


router = APIRouter()


@router.get("", response_model=list[FileTagItem])
def list_tags(
    with_usage: bool = Query(default=False),
    include_unused: bool = Query(default=True),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> list[FileTagItem]:
    """读取当前会话可见的活动标签。"""

    return FileService(db, settings).list_tags(
        current_user=current_user,
        with_usage=with_usage,
        include_unused=include_unused,
    )


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


@router.post("/import", response_model=FileTagImportResponse)
def import_tags(
    payload: FileTagImportRequest,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> FileTagImportResponse:
    """按指定分隔符批量导入标签。"""

    return FileService(db, settings).import_tags(
        payload=payload,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.get("/{tag_id}/files", response_model=FileSearchResponse)
def list_files_by_tag(
    tag_id: str,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> FileSearchResponse:
    """读取标签关联的当前会话可见文件。"""

    return FileService(db, settings).list_files_by_tag(
        tag_id=tag_id,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.patch("/{tag_id}", response_model=FileTagItem)
def update_tag(
    tag_id: str,
    payload: FileTagUpdateRequest,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> FileTagItem:
    """更新标签基础信息。"""

    return FileService(db, settings).update_tag(
        tag_id=tag_id,
        payload=payload,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: str,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> None:
    """停用标签并移除文件关联。"""

    FileService(db, settings).delete_tag(
        tag_id=tag_id,
        current_user=current_user,
        client_ip=client_ip,
    )
