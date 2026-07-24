from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_client_ip, get_current_user, get_db_session
from app.core.config import Settings, get_settings
from app.models.user import UserAccount
from app.schemas.file import FileUploadResponse, MarkdownReadResponse
from app.services.file_service import FileService


router = APIRouter()


@router.get("", response_model=list[FileUploadResponse])
def list_files(
    path_id: str = Query(default="root"),
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> list[FileUploadResponse]:
    """按目录读取文件列表；show_hidden 未传时按系统隐藏配置过滤。"""

    return FileService(db, settings).list_files(
        path_id=path_id,
        show_hidden=show_hidden,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    path_id: str = Form(default="root"),
    encryption_enabled: bool | None = Form(default=None),
    is_hidden: bool = Form(default=False),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> FileUploadResponse:
    """上传文件，后端分块读取并按配置可选加密。"""

    return await FileService(db, settings).upload_file(
        upload_file=file,
        path_id=path_id,
        current_user=current_user,
        client_ip=client_ip,
        encryption_enabled=encryption_enabled,
        is_hidden=is_hidden,
    )


@router.get("/{file_id}/markdown", response_model=MarkdownReadResponse)
def read_markdown(
    file_id: str,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> MarkdownReadResponse:
    """读取 Markdown 文件内容，接口只支持 .md/.markdown 或 text/markdown。"""

    return FileService(db, settings).read_markdown(
        file_id=file_id,
        current_user=current_user,
        client_ip=client_ip,
    )
