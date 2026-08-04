from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_client_ip, get_current_user, get_db_session
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, AuthenticationError
from app.models.user import UserAccount
from app.schemas.file import (
    DocumentCreateRequest,
    DocumentConvertRequest,
    DocumentMergeRequest,
    DocumentReadResponse,
    DocumentSaveRequest,
    FileConflictStrategy,
    FileDetailResponse,
    FileExportRequest,
    FileListItem,
    FileMoveRequest,
    FilePreviewTokenResponse,
    FileSearchResponse,
    FileTagsUpdateRequest,
    FileUpdateRequest,
    FileUploadResponse,
    MarkdownReadResponse,
    TextReadResponse,
)
from app.services.file_service import FileService
from app.services.storage_service import ContentRange


router = APIRouter()


def _parse_range_header(range_header: str | None, total_size: int) -> ContentRange | None:
    if not range_header:
        return None
    if not range_header.startswith("bytes=") or "," in range_header:
        raise AppError("不支持的 Range 请求", status_code=416, error_code="range_not_satisfiable")

    raw_range = range_header.removeprefix("bytes=").strip()
    start_text, separator, end_text = raw_range.partition("-")
    if separator != "-":
        raise AppError("不支持的 Range 请求", status_code=416, error_code="range_not_satisfiable")

    if start_text == "":
        suffix_length = int(end_text) if end_text.isdigit() else 0
        if suffix_length <= 0:
            raise AppError("不支持的 Range 请求", status_code=416, error_code="range_not_satisfiable")
        start = max(total_size - suffix_length, 0)
        end = total_size - 1
    else:
        if not start_text.isdigit():
            raise AppError("不支持的 Range 请求", status_code=416, error_code="range_not_satisfiable")
        start = int(start_text)
        end = int(end_text) if end_text.isdigit() else total_size - 1

    if total_size <= 0 or start >= total_size or end < start:
        raise AppError("请求范围超出文件大小", status_code=416, error_code="range_not_satisfiable")
    return ContentRange(start=start, end=min(end, total_size - 1), total=total_size)


@router.get("", response_model=list[FileListItem])
def list_files(
    path_id: str = Query(default="root"),
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> list[FileListItem]:
    """按目录读取文件列表，是否包含隐藏文件由当前会话开关决定。"""

    return FileService(db, settings).list_files(
        path_id=path_id,
        show_hidden=show_hidden,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.get("/search", response_model=FileSearchResponse)
def search_files(
    q: str = Query(min_length=1, max_length=200),
    show_hidden: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> FileSearchResponse:
    """按文件名、备注、摘要、类型和标签搜索元数据。"""

    return FileService(db, settings).search_files(
        query=q,
        show_hidden=show_hidden,
        limit=limit,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.post("/export")
def export_files(
    payload: FileExportRequest,
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> StreamingResponse:
    """导出所选文件；单文件返回本体，多文件返回 zip。"""

    filename, media_type, content_length, chunks = FileService(db, settings).export_files_content(
        payload=payload,
        show_hidden=show_hidden,
        current_user=current_user,
        client_ip=client_ip,
    )
    quoted_name = quote(filename)
    return StreamingResponse(
        chunks,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted_name}",
            "Content-Length": str(content_length),
        },
    )


@router.get("/{file_id}/export")
def export_file(
    file_id: str,
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> StreamingResponse:
    """导出单个文件本体，按需解密后返回。"""

    file_info, chunks = FileService(db, settings).export_file_content(
        file_id=file_id,
        show_hidden=show_hidden,
        current_user=current_user,
        client_ip=client_ip,
    )
    media_type = file_info.mime_type or "application/octet-stream"
    quoted_name = quote(file_info.original_name)
    return StreamingResponse(
        chunks,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted_name}",
            "Content-Length": str(file_info.size_bytes),
        },
    )


@router.get("/{file_id}/preview")
def preview_file(
    file_id: str,
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> StreamingResponse:
    """图片/PDF 只读预览流，按需解密后返回。"""

    file_info, chunks = FileService(db, settings).preview_content(
        file_id=file_id,
        show_hidden=show_hidden,
        current_user=current_user,
        client_ip=client_ip,
    )
    media_type = file_info.mime_type or ("application/pdf" if file_info.file_type == "pdf" else "application/octet-stream")
    quoted_name = quote(file_info.original_name)
    return StreamingResponse(
        chunks,
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quoted_name}"},
    )


@router.post("/{file_id}/preview-token", response_model=FilePreviewTokenResponse)
def issue_preview_token(
    file_id: str,
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> FilePreviewTokenResponse:
    """签发短时效视频预览链接，供原生 video 标签播放。"""

    return FileService(db, settings).issue_preview_token(
        file_id=file_id,
        show_hidden=show_hidden,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.get("/{file_id}/video-stream")
def stream_video(
    file_id: str,
    request: Request,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> StreamingResponse:
    """支持 HTTP Range 的视频明文流，Token 仅用于短时效预览。"""

    if not token:
        raise AuthenticationError("视频预览链接无效或已过期")
    service = FileService(db, settings)
    file_info = service.repository.get_active_by_file_id(file_id)
    if file_info is None:
        raise AppError("文件不存在", status_code=404, error_code="not_found")
    content_range = _parse_range_header(request.headers.get("range"), file_info.size_bytes)
    file_info, chunks, selected_range = service.stream_video_content(
        file_id=file_id,
        token=token,
        content_range=content_range,
        client_ip=client_ip,
    )
    media_type = file_info.mime_type or "application/octet-stream"
    quoted_name = quote(file_info.original_name)
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f"inline; filename*=UTF-8''{quoted_name}",
        "Content-Length": str(selected_range.length if selected_range else file_info.size_bytes),
    }
    status_code = status.HTTP_206_PARTIAL_CONTENT if selected_range else status.HTTP_200_OK
    if selected_range:
        headers["Content-Range"] = f"bytes {selected_range.start}-{selected_range.end}/{file_info.size_bytes}"
    return StreamingResponse(chunks, status_code=status_code, media_type=media_type, headers=headers)


@router.post("/merge", response_model=FileDetailResponse, status_code=status.HTTP_201_CREATED)
def merge_documents(
    payload: DocumentMergeRequest,
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> FileDetailResponse:
    """将选中的多个文档合并为同目录新文件。"""

    return FileService(db, settings).merge_documents(
        payload=payload,
        show_hidden=show_hidden,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.post("/document", response_model=FileDetailResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: DocumentCreateRequest,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> FileDetailResponse:
    """创建空白文本、Markdown 或 HTML 文档。"""

    return FileService(db, settings).create_document(
        payload=payload,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.get("/{file_id}", response_model=FileDetailResponse)
def get_file_detail(
    file_id: str,
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> FileDetailResponse:
    """读取文件详情元数据，不暴露后端存储对象名或物理路径。"""

    return FileService(db, settings).get_file_detail(
        file_id=file_id,
        show_hidden=show_hidden,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.patch("/{file_id}/move", response_model=FileDetailResponse)
def move_file(
    file_id: str,
    payload: FileMoveRequest,
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> FileDetailResponse:
    """移动文件到指定目录。"""

    return FileService(db, settings).move_file(
        file_id=file_id,
        payload=payload,
        show_hidden=show_hidden,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.patch("/{file_id}", response_model=FileDetailResponse)
def update_file_remark(
    file_id: str,
    payload: FileUpdateRequest,
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> FileDetailResponse:
    """更新文件备注，并返回更新后的文件详情。"""

    return FileService(db, settings).update_file_remark(
        file_id=file_id,
        payload=payload,
        show_hidden=show_hidden,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.get("/{file_id}/document", response_model=DocumentReadResponse)
def read_document(
    file_id: str,
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> DocumentReadResponse:
    """统一读取纯文本、Markdown 和 HTML 文档。"""

    return FileService(db, settings).read_document(
        file_id=file_id,
        show_hidden=show_hidden,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.put("/{file_id}/document", response_model=DocumentReadResponse)
def save_document(
    file_id: str,
    payload: DocumentSaveRequest,
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> DocumentReadResponse:
    """保存当前文档内容，保持原文件格式。"""

    return FileService(db, settings).save_document(
        file_id=file_id,
        payload=payload,
        show_hidden=show_hidden,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.post("/{file_id}/convert", response_model=FileDetailResponse, status_code=status.HTTP_201_CREATED)
def convert_document(
    file_id: str,
    payload: DocumentConvertRequest,
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> FileDetailResponse:
    """将当前文档转换为同目录新文件。"""

    return FileService(db, settings).convert_document(
        file_id=file_id,
        payload=payload,
        show_hidden=show_hidden,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.put("/{file_id}/tags", response_model=FileDetailResponse)
def update_file_tags(
    file_id: str,
    payload: FileTagsUpdateRequest,
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> FileDetailResponse:
    """替换文件标签集合。"""

    return FileService(db, settings).update_file_tags(
        file_id=file_id,
        payload=payload,
        show_hidden=show_hidden,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    file_id: str,
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> None:
    """删除文件。"""

    FileService(db, settings).delete_file(
        file_id=file_id,
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
    conflict_strategy: FileConflictStrategy = Form(default="rename"),
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
        conflict_strategy=conflict_strategy,
    )


@router.get("/{file_id}/markdown", response_model=MarkdownReadResponse)
def read_markdown(
    file_id: str,
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> MarkdownReadResponse:
    """读取 Markdown 文件内容，接口只支持 .md/.markdown 或 text/markdown。"""

    return FileService(db, settings).read_markdown(
        file_id=file_id,
        show_hidden=show_hidden,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.get("/{file_id}/text", response_model=TextReadResponse)
def read_text(
    file_id: str,
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> TextReadResponse:
    """读取纯文本文件内容，支持 txt/log/csv/json 等文本型文件。"""

    return FileService(db, settings).read_text(
        file_id=file_id,
        show_hidden=show_hidden,
        current_user=current_user,
        client_ip=client_ip,
    )
