import logging
import re
import zipfile
from datetime import timedelta, timezone
from html import escape
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import jwt
from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, UnsupportedFileTypeError
from app.core.security import now_utc
from app.models.file import FileInfo, FilePath, FileTag
from app.models.user import UserAccount
from app.repositories.file_repository import FileRepository, FileTagRepository
from app.repositories.path_repository import PathRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.file import (
    DocumentCreateRequest,
    DocumentConvertRequest,
    DocumentMergeRequest,
    DocumentReadResponse,
    DocumentSaveRequest,
    FileBatchDeleteRequest,
    FileConflictStrategy,
    FileDetailResponse,
    FileEmbedTokenResponse,
    FileExportRequest,
    FileListItem,
    FileMoveRequest,
    FilePreviewTokenResponse,
    FileSearchResponse,
    FileTagCreateRequest,
    FileTagItem,
    FileTagsUpdateRequest,
    FileUpdateRequest,
    FileUploadResponse,
    MarkdownReadResponse,
    TextReadResponse,
)
from app.services.audit_service import AuditService
from app.services.setting_service import SettingService
from app.services.storage_service import ContentRange, StorageService, StoredObject
from app.utils.file_type import (
    detect_document_format,
    detect_file_type,
    document_format_extension,
    document_format_mime_type,
    is_markdown_file,
    is_text_file,
    normalize_extension,
)
from app.utils.ids import new_business_id


class _PlainTextExtractor(HTMLParser):
    """从 HTML 中提取用于 plain text / Markdown 转换的可读文本。"""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        lines = [line.strip() for line in "".join(self.parts).splitlines()]
        return "\n".join(line for line in lines if line)


class FileService:
    """文件服务，编排上传、加密存储、元数据和 Markdown 读取。"""

    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.repository = FileRepository(db)
        self.tag_repository = FileTagRepository(db)
        self.path_repository = PathRepository(db)
        self.session_repository = SessionRepository(db)
        self.setting_service = SettingService(db)
        self.audit_service = AuditService(db)
        self.storage_service = StorageService(settings)
        self.logger = logging.getLogger("pfmt.business")

    def issue_preview_token(
        self,
        *,
        file_id: str,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> FilePreviewTokenResponse:
        """签发短时效视频预览 Token，供原生 video 标签使用。"""

        file_info, _parent_path = self._get_visible_file_and_path(
            file_id=file_id,
            show_hidden=show_hidden,
            action_type="issue_preview_token",
            current_user=current_user,
            client_ip=client_ip,
        )
        if file_info.file_type != "video":
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="issue_preview_token",
                target_type="file",
                target_id=file_id,
                result="failed",
                detail={"reason": "unsupported_file_type"},
                client_ip=client_ip,
            )
            self.db.commit()
            raise UnsupportedFileTypeError("当前文件类型暂不支持视频播放")

        expires_at = now_utc() + timedelta(minutes=5)
        payload: dict[str, Any] = {
            "sub": current_user.user_id,
            "sid": getattr(current_user, "_pfmt_session_id", None),
            "fid": file_id,
            "purpose": "video_preview",
            "show_hidden": self._include_hidden_files(current_user=current_user),
            "jti": uuid4().hex,
            "exp": expires_at.replace(tzinfo=timezone.utc),
            "iat": now_utc().replace(tzinfo=timezone.utc),
        }
        token = jwt.encode(payload, self.settings.effective_jwt_secret, algorithm=self.settings.jwt_algorithm)
        self.audit_service.record(
            user_id=current_user.user_id,
            action_type="issue_preview_token",
            target_type="file",
            target_id=file_id,
            result="success",
            detail={"purpose": "video_preview", "show_hidden": payload["show_hidden"]},
            client_ip=client_ip,
        )
        self.db.commit()
        return FilePreviewTokenResponse(
            file_id=file_id,
            preview_url=f"/api/files/{file_id}/video-stream?token={token}",
            expires_at=expires_at,
        )

    def issue_embed_token(
        self,
        *,
        file_id: str,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> FileEmbedTokenResponse:
        """签发短时效嵌入访问令牌，供文档内 <img>/<a> 无需登录头读取文件。"""

        file_info, _parent_path = self._get_visible_file_and_path(
            file_id=file_id,
            show_hidden=show_hidden,
            action_type="issue_embed_token",
            current_user=current_user,
            client_ip=client_ip,
        )
        expires_at = now_utc() + timedelta(minutes=self.settings.embed_token_minutes)
        payload: dict[str, Any] = {
            "sub": current_user.user_id,
            "sid": getattr(current_user, "_pfmt_session_id", None),
            "fid": file_id,
            "purpose": "embed",
            "show_hidden": self._include_hidden_files(current_user=current_user),
            "jti": uuid4().hex,
            "exp": expires_at.replace(tzinfo=timezone.utc),
            "iat": now_utc().replace(tzinfo=timezone.utc),
        }
        token = jwt.encode(payload, self.settings.effective_jwt_secret, algorithm=self.settings.jwt_algorithm)
        self.audit_service.record(
            user_id=current_user.user_id,
            action_type="issue_embed_token",
            target_type="file",
            target_id=file_id,
            result="success",
            detail={"file_type": file_info.file_type, "show_hidden": payload["show_hidden"]},
            client_ip=client_ip,
        )
        self.db.commit()
        return FileEmbedTokenResponse(
            file_id=file_id,
            url=f"/api/files/{file_id}/stream?token={token}",
            expires_at=expires_at,
        )

    def stream_video_content(
        self,
        *,
        file_id: str,
        token: str,
        content_range: ContentRange | None,
        client_ip: str | None,
    ) -> tuple[FileInfo, Iterator[bytes], ContentRange | None]:
        """校验短期 Token 后返回视频明文流。"""

        payload = self._decode_preview_token(token=token, file_id=file_id)
        user_id = str(payload["sub"])
        session_id = str(payload["sid"])
        session = self.session_repository.get_active(session_id)
        if session is None or session.user_id != user_id:
            raise AuthenticationError("视频预览链接无效或已过期")
        include_hidden = self.setting_service.get_bool("hidden.feature_enabled", True) and bool(session.show_hidden_enabled)
        file_info, parent_path = self._get_visible_file_for_token(
            file_id=file_id,
            include_hidden=include_hidden,
            user_id=user_id,
            client_ip=client_ip,
            action_type="stream_video",
        )
        if file_info.file_type != "video":
            self.audit_service.record(
                user_id=user_id,
                action_type="stream_video",
                target_type="file",
                target_id=file_id,
                result="failed",
                detail={"reason": "unsupported_file_type"},
                client_ip=client_ip,
            )
            self.db.commit()
            raise UnsupportedFileTypeError("当前文件类型暂不支持视频播放")

        selected_range = content_range
        if selected_range is not None and selected_range.total != file_info.size_bytes:
            selected_range = ContentRange(start=selected_range.start, end=selected_range.end, total=file_info.size_bytes)

        chunks = (
            self.storage_service.iter_plain_range(file_info, selected_range)
            if selected_range is not None
            else self.storage_service.iter_content_chunks(file_info)
        )
        self.repository.mark_accessed(file_info)
        self.audit_service.record(
            user_id=user_id,
            action_type="stream_video",
            target_type="file",
            target_id=file_id,
            result="success",
            detail={
                "range_start": selected_range.start if selected_range else None,
                "range_end": selected_range.end if selected_range else None,
                "size_bytes": file_info.size_bytes,
            },
            client_ip=client_ip,
        )
        self.db.commit()
        return file_info, chunks, selected_range

    def stream_embed_content(
        self,
        *,
        file_id: str,
        token: str,
        client_ip: str | None,
    ) -> tuple[FileInfo, Iterator[bytes]]:
        """校验嵌入令牌后返回任意文件明文流，供文档内图片/附件引用。"""

        payload = self._decode_preview_token(token=token, file_id=file_id, purpose="embed")
        user_id = str(payload["sub"])
        session_id = str(payload["sid"])
        session = self.session_repository.get_active(session_id)
        if session is None or session.user_id != user_id:
            raise AuthenticationError("嵌入访问链接无效或已过期")
        include_hidden = self.setting_service.get_bool("hidden.feature_enabled", True) and bool(session.show_hidden_enabled)
        file_info, parent_path = self._get_visible_file_for_token(
            file_id=file_id,
            include_hidden=include_hidden,
            user_id=user_id,
            client_ip=client_ip,
            action_type="stream_embed",
        )
        self.repository.mark_accessed(file_info)
        self.audit_service.record(
            user_id=user_id,
            action_type="stream_embed",
            target_type="file",
            target_id=file_id,
            result="success",
            detail={"file_type": file_info.file_type, "size_bytes": file_info.size_bytes},
            client_ip=client_ip,
        )
        self.db.commit()
        return file_info, self.storage_service.iter_content_chunks(file_info)

    async def upload_file(
        self,
        *,
        upload_file: UploadFile,
        path_id: str,
        current_user: UserAccount,
        client_ip: str | None,
        encryption_enabled: bool | None,
        is_hidden: bool,
        conflict_strategy: FileConflictStrategy = "rename",
    ) -> FileUploadResponse:
        """上传文件：先流式落盘，再在同一事务内写元数据和审计。"""

        parent_path = self.path_repository.get_active_by_path_id(path_id)
        if parent_path is None:
            self._record_failed_upload(current_user.user_id, client_ip, "path_not_found")
            raise NotFoundError("目录不存在")

        file_id = new_business_id("file")
        original_name = Path(upload_file.filename or "unnamed").name or "unnamed"
        file_ext = normalize_extension(original_name)
        mime_type = upload_file.content_type
        auto_converted_txt_to_md = False
        if file_ext == ".txt" and self.setting_service.get_bool("document.auto_convert_txt_to_md", False):
            original_name = f"{Path(original_name).stem}.md"
            file_ext = ".md"
            mime_type = "text/markdown"
            auto_converted_txt_to_md = True
        file_type = detect_file_type(file_ext, mime_type)
        existing_file = self.repository.get_active_by_name(path_id=parent_path.path_id, original_name=original_name)
        should_encrypt = (
            self.setting_service.get_bool("storage.encryption_enabled", True)
            if encryption_enabled is None
            else encryption_enabled
        )

        if existing_file is not None and conflict_strategy == "overwrite":
            old_storage_path = existing_file.storage_path
            try:
                stored_object = await self.storage_service.save_upload_file(
                    upload_file=upload_file,
                    file_id=existing_file.file_id,
                    encryption_enabled=should_encrypt,
                    parent_storage_path=parent_path.storage_path,
                )
                self.repository.update_upload_content_metadata(
                    existing_file,
                    mime_type=mime_type,
                    file_ext=file_ext,
                    file_type=file_type,
                    storage_object_name=stored_object.storage_object_name,
                    storage_path=stored_object.storage_path,
                    size_bytes=stored_object.size_bytes,
                    checksum_sha256=stored_object.checksum_sha256,
                    encryption_enabled=should_encrypt,
                    key_wrap_version=stored_object.key_wrap_version,
                    key_id=stored_object.key_id,
                    is_hidden=is_hidden,
                    user_id=current_user.user_id,
                )
                self.audit_service.record(
                    user_id=current_user.user_id,
                    action_type="upload_file",
                    target_type="file",
                    target_id=existing_file.file_id,
                    result="success",
                    detail={
                        "path_id": parent_path.path_id,
                        "file_type": file_type,
                        "size_bytes": stored_object.size_bytes,
                        "encryption_enabled": should_encrypt,
                        "conflict_strategy": conflict_strategy,
                        "auto_converted_txt_to_md": auto_converted_txt_to_md,
                    },
                    client_ip=client_ip,
                )
                self.db.commit()
                self.db.refresh(existing_file)
                if old_storage_path != stored_object.storage_path:
                    self.storage_service.delete_object(old_storage_path)
                self.logger.info(
                    "文件覆盖上传完成",
                    extra={
                        "action": "upload_file",
                        "target_type": "file",
                        "target_id": existing_file.file_id,
                        "result": "success",
                    },
                )
                return self._to_upload_response(existing_file)
            except Exception:
                self.db.rollback()
                self._record_failed_upload(current_user.user_id, client_ip, "upload_failed")
                raise

        original_name = self._available_file_name(parent_path.path_id, original_name)
        file_ext = normalize_extension(original_name)
        file_type = detect_file_type(file_ext, mime_type)

        stored_object: StoredObject | None = None
        try:
            stored_object = await self.storage_service.save_upload_file(
                upload_file=upload_file,
                file_id=file_id,
                encryption_enabled=should_encrypt,
                parent_storage_path=parent_path.storage_path,
            )
            file_info = FileInfo(
                file_id=file_id,
                path_id=parent_path.path_id,
                original_name=original_name,
                storage_object_name=stored_object.storage_object_name,
                storage_path=stored_object.storage_path,
                storage_provider="local",
                mime_type=mime_type,
                file_ext=file_ext,
                file_type=file_type,
                size_bytes=stored_object.size_bytes,
                checksum_sha256=stored_object.checksum_sha256,
                encryption_enabled=should_encrypt,
                key_wrap_version=stored_object.key_wrap_version,
                key_id=stored_object.key_id,
                is_hidden=is_hidden,
                visibility_type="normal",
                created_by=current_user.user_id,
                updated_by=current_user.user_id,
            )
            self.repository.create(file_info)
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="upload_file",
                target_type="file",
                target_id=file_id,
                result="success",
                detail={
                    "path_id": parent_path.path_id,
                    "file_type": file_type,
                    "size_bytes": stored_object.size_bytes,
                    "encryption_enabled": should_encrypt,
                    "auto_converted_txt_to_md": auto_converted_txt_to_md,
                },
                client_ip=client_ip,
            )
            self.db.commit()
            self.db.refresh(file_info)
            self.logger.info(
                "文件上传完成",
                extra={"action": "upload_file", "target_type": "file", "target_id": file_id, "result": "success"},
            )
            return self._to_upload_response(file_info)
        except IntegrityError as exc:
            self.db.rollback()
            if stored_object is not None:
                self.storage_service.delete_object(stored_object.storage_path)
            self._record_failed_upload(current_user.user_id, client_ip, "metadata_conflict")
            raise ConflictError("文件元数据写入冲突") from exc
        except Exception:
            self.db.rollback()
            if stored_object is not None:
                self.storage_service.delete_object(stored_object.storage_path)
            self._record_failed_upload(current_user.user_id, client_ip, "upload_failed")
            raise

    def create_document(
        self,
        *,
        payload: DocumentCreateRequest,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> FileDetailResponse:
        """创建空白文档，复用随机对象名和可选加密写入链路。"""

        parent_path = self.path_repository.get_active_by_path_id(payload.path_id)
        if parent_path is None:
            self._record_file_action_failure(
                user_id=current_user.user_id,
                client_ip=client_ip,
                file_id="",
                action_type="create_document",
                reason="path_not_found",
            )
            raise NotFoundError("目录不存在")

        target_name = payload.original_name
        target_ext = normalize_extension(target_name)
        expected_ext = document_format_extension(payload.document_format)
        if target_ext != expected_ext:
            target_name = f"{Path(target_name).stem}{expected_ext}"

        created_file: FileInfo | None = None
        try:
            created_file = self._create_generated_document_file(
                path_id=parent_path.path_id,
                target_name=target_name,
                target_format=payload.document_format,
                content="",
                current_user=current_user,
                is_hidden=payload.is_hidden,
            )
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="create_document",
                target_type="file",
                target_id=created_file.file_id,
                result="success",
                detail={
                    "path_id": parent_path.path_id,
                    "document_format": payload.document_format,
                    "is_hidden": payload.is_hidden,
                },
                client_ip=client_ip,
            )
            self.db.commit()
            self.db.refresh(created_file)
            return self._to_detail_response(created_file, parent_path)
        except Exception:
            self.db.rollback()
            if created_file is not None:
                self.storage_service.delete_object(created_file.storage_path)
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="create_document",
                target_type="file",
                result="failed",
                detail={"reason": "create_failed", "path_id": parent_path.path_id},
                client_ip=client_ip,
            )
            self.db.commit()
            raise

    def read_markdown(
        self,
        *,
        file_id: str,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> MarkdownReadResponse:
        """读取 Markdown 文件，必要时按加密 envelope 分块解密。"""

        file_info, _parent_path = self._get_visible_file_and_path(
            file_id=file_id,
            show_hidden=show_hidden,
            action_type="read_markdown",
            current_user=current_user,
            client_ip=client_ip,
        )

        if not is_markdown_file(file_info.file_ext, file_info.mime_type):
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="read_markdown",
                target_type="file",
                target_id=file_id,
                result="failed",
                detail={"reason": "unsupported_file_type"},
                client_ip=client_ip,
            )
            self.db.commit()
            raise UnsupportedFileTypeError("仅支持 Markdown 文件读取")

        try:
            content = self._read_text_content(file_info)
            self.repository.mark_accessed(file_info)
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="read_markdown",
                target_type="file",
                target_id=file_id,
                result="success",
                detail={"size_bytes": file_info.size_bytes},
                client_ip=client_ip,
            )
            self.db.commit()
            return MarkdownReadResponse(
                file_id=file_info.file_id,
                original_name=file_info.original_name,
                mime_type=file_info.mime_type,
                size_bytes=file_info.size_bytes,
                content=content,
            )
        except Exception:
            self.db.rollback()
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="read_markdown",
                target_type="file",
                target_id=file_id,
                result="failed",
                detail={"reason": "read_failed"},
                client_ip=client_ip,
            )
            self.db.commit()
            raise

    def read_document(
        self,
        *,
        file_id: str,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> DocumentReadResponse:
        """统一读取可编辑文档，覆盖纯文本、Markdown 和 HTML。"""

        file_info, _parent_path = self._get_visible_file_and_path(
            file_id=file_id,
            show_hidden=show_hidden,
            action_type="read_document",
            current_user=current_user,
            client_ip=client_ip,
        )
        document_format = detect_document_format(file_info.file_ext, file_info.mime_type)
        if not document_format or not is_text_file(file_info.file_ext, file_info.mime_type, file_info.file_type):
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="read_document",
                target_type="file",
                target_id=file_id,
                result="failed",
                detail={"reason": "unsupported_file_type"},
                client_ip=client_ip,
            )
            self.db.commit()
            raise UnsupportedFileTypeError("当前文件类型暂不支持文档编辑")

        try:
            content = self._read_text_content(file_info)
            self.repository.mark_accessed(file_info)
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="read_document",
                target_type="file",
                target_id=file_id,
                result="success",
                detail={"document_format": document_format, "size_bytes": file_info.size_bytes},
                client_ip=client_ip,
            )
            self.db.commit()
            return DocumentReadResponse(
                file_id=file_info.file_id,
                original_name=file_info.original_name,
                mime_type=file_info.mime_type,
                size_bytes=file_info.size_bytes,
                document_format=document_format,
                content=content,
                rendered_html=self._render_document_html(content, document_format),
            )
        except Exception:
            self.db.rollback()
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="read_document",
                target_type="file",
                target_id=file_id,
                result="failed",
                detail={"reason": "read_failed"},
                client_ip=client_ip,
            )
            self.db.commit()
            raise

    def save_document(
        self,
        *,
        file_id: str,
        payload: DocumentSaveRequest,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> DocumentReadResponse:
        """保存统一文档内容，保持当前文件格式不变。"""

        file_info, _parent_path = self._get_visible_file_and_path(
            file_id=file_id,
            show_hidden=show_hidden,
            action_type="save_document",
            current_user=current_user,
            client_ip=client_ip,
        )
        document_format = detect_document_format(file_info.file_ext, file_info.mime_type)
        if document_format is None or document_format != payload.document_format:
            self._record_file_action_failure(
                user_id=current_user.user_id,
                client_ip=client_ip,
                file_id=file_id,
                action_type="save_document",
                reason="document_format_mismatch",
            )
            raise UnsupportedFileTypeError("保存格式必须与当前文件格式一致")

        content_bytes = payload.content.encode("utf-8")
        try:
            stored_object = self.storage_service.replace_file_content(file_info=file_info, content=content_bytes)
            self.repository.update_content_metadata(
                file_info,
                size_bytes=stored_object.size_bytes,
                checksum_sha256=stored_object.checksum_sha256,
                key_wrap_version=stored_object.key_wrap_version,
                key_id=stored_object.key_id,
                user_id=current_user.user_id,
            )
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="save_document",
                target_type="file",
                target_id=file_id,
                result="success",
                detail={"document_format": document_format, "size_bytes": stored_object.size_bytes},
                client_ip=client_ip,
            )
            self.db.commit()
            self.db.refresh(file_info)
            return DocumentReadResponse(
                file_id=file_info.file_id,
                original_name=file_info.original_name,
                mime_type=file_info.mime_type,
                size_bytes=file_info.size_bytes,
                document_format=document_format,
                content=payload.content,
                rendered_html=self._render_document_html(payload.content, document_format),
            )
        except Exception:
            self.db.rollback()
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="save_document",
                target_type="file",
                target_id=file_id,
                result="failed",
                detail={"reason": "save_failed"},
                client_ip=client_ip,
            )
            self.db.commit()
            raise

    def convert_document(
        self,
        *,
        file_id: str,
        payload: DocumentConvertRequest,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> FileDetailResponse:
        """将文档转换为新文件，默认不覆盖原文件。"""

        file_info, parent_path = self._get_visible_file_and_path(
            file_id=file_id,
            show_hidden=show_hidden,
            action_type="convert_document",
            current_user=current_user,
            client_ip=client_ip,
        )
        source_format = detect_document_format(file_info.file_ext, file_info.mime_type)
        if source_format is None:
            self._record_file_action_failure(
                user_id=current_user.user_id,
                client_ip=client_ip,
                file_id=file_id,
                action_type="convert_document",
                reason="unsupported_file_type",
            )
            raise UnsupportedFileTypeError("当前文件类型暂不支持转换")

        source_content = self._read_text_content(file_info)
        converted_content = self._convert_document_content(source_content, source_format, payload.target_format)
        target_name = payload.target_name or self._default_converted_name(file_info.original_name, payload.target_format)
        target_ext = normalize_extension(target_name)
        expected_ext = document_format_extension(payload.target_format)
        if target_ext != expected_ext:
            target_name = f"{Path(target_name).stem}{expected_ext}"
        converted_file: FileInfo | None = None
        try:
            converted_file = self._create_generated_document_file(
                path_id=file_info.path_id,
                target_name=target_name,
                target_format=payload.target_format,
                content=converted_content,
                current_user=current_user,
                source_file=file_info,
            )
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="convert_document",
                target_type="file",
                target_id=converted_file.file_id,
                result="success",
                detail={"source_file_id": file_id, "source_format": source_format, "target_format": payload.target_format},
                client_ip=client_ip,
            )
            self.db.commit()
            self.db.refresh(converted_file)
            return self._to_detail_response(converted_file, parent_path)
        except Exception:
            self.db.rollback()
            if converted_file is not None:
                self.storage_service.delete_object(converted_file.storage_path)
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="convert_document",
                target_type="file",
                target_id=file_id,
                result="failed",
                detail={"reason": "convert_failed"},
                client_ip=client_ip,
            )
            self.db.commit()
            raise

    def merge_documents(
        self,
        *,
        payload: DocumentMergeRequest,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> FileDetailResponse:
        """按传入顺序将多个统一文档合并为同目录新文件。"""

        source_files: list[tuple[FileInfo, str, str]] = []
        parent_path: FilePath | None = None
        for file_id in payload.file_ids:
            file_info, current_parent_path = self._get_visible_file_and_path(
                file_id=file_id,
                show_hidden=show_hidden,
                action_type="merge_documents",
                current_user=current_user,
                client_ip=client_ip,
            )
            source_format = detect_document_format(file_info.file_ext, file_info.mime_type)
            if source_format is None:
                self._record_file_action_failure(
                    user_id=current_user.user_id,
                    client_ip=client_ip,
                    file_id=file_id,
                    action_type="merge_documents",
                    reason="unsupported_file_type",
                )
                raise UnsupportedFileTypeError("只能合并文本、Markdown 或 HTML 文档")
            content = self._read_text_content(file_info)
            source_files.append((file_info, source_format, content))
            parent_path = parent_path or current_parent_path

        if parent_path is None:
            raise NotFoundError("文件不存在")

        merged_content = self._merge_document_contents(source_files, payload.target_format)
        target_name = payload.target_name or f"合并文档{document_format_extension(payload.target_format)}"
        target_ext = normalize_extension(target_name)
        expected_ext = document_format_extension(payload.target_format)
        if target_ext != expected_ext:
            target_name = f"{Path(target_name).stem}{expected_ext}"

        merged_file: FileInfo | None = None
        try:
            merged_file = self._create_generated_document_file(
                path_id=parent_path.path_id,
                target_name=target_name,
                target_format=payload.target_format,
                content=merged_content,
                current_user=current_user,
            )
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="merge_documents",
                target_type="file",
                target_id=merged_file.file_id,
                result="success",
                detail={
                    "source_file_ids": payload.file_ids,
                    "target_format": payload.target_format,
                    "source_count": len(source_files),
                },
                client_ip=client_ip,
            )
            self.db.commit()
            self.db.refresh(merged_file)
            return self._to_detail_response(merged_file, parent_path)
        except Exception:
            self.db.rollback()
            if merged_file is not None:
                self.storage_service.delete_object(merged_file.storage_path)
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="merge_documents",
                target_type="file",
                result="failed",
                detail={"reason": "merge_failed", "source_file_ids": payload.file_ids},
                client_ip=client_ip,
            )
            self.db.commit()
            raise

    def read_text(
        self,
        *,
        file_id: str,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> TextReadResponse:
        """读取普通文本文件，按既有存储管线解密后返回只读内容。"""

        file_info, _parent_path = self._get_visible_file_and_path(
            file_id=file_id,
            show_hidden=show_hidden,
            action_type="read_text",
            current_user=current_user,
            client_ip=client_ip,
        )

        if not is_text_file(file_info.file_ext, file_info.mime_type, file_info.file_type):
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="read_text",
                target_type="file",
                target_id=file_id,
                result="failed",
                detail={"reason": "unsupported_file_type"},
                client_ip=client_ip,
            )
            self.db.commit()
            raise UnsupportedFileTypeError("仅支持纯文本文件读取")

        try:
            content = self._read_text_content(file_info)
            self.repository.mark_accessed(file_info)
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="read_text",
                target_type="file",
                target_id=file_id,
                result="success",
                detail={"size_bytes": file_info.size_bytes},
                client_ip=client_ip,
            )
            self.db.commit()
            return TextReadResponse(
                file_id=file_info.file_id,
                original_name=file_info.original_name,
                mime_type=file_info.mime_type,
                size_bytes=file_info.size_bytes,
                content=content,
            )
        except Exception:
            self.db.rollback()
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="read_text",
                target_type="file",
                target_id=file_id,
                result="failed",
                detail={"reason": "read_failed"},
                client_ip=client_ip,
            )
            self.db.commit()
            raise

    def list_files(
        self,
        *,
        path_id: str,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> list[FileListItem]:
        """读取指定目录下的文件元数据列表，前端用它展示文件列表和逻辑地址。"""

        include_hidden = self._include_hidden_files(current_user=current_user)
        parent_path = self.path_repository.get_active_by_path_id(path_id)
        if parent_path is None:
            self._record_failed_list(current_user.user_id, client_ip, path_id, "path_not_found")
            raise NotFoundError("目录不存在")

        if parent_path.is_hidden and not include_hidden:
            self._record_failed_list(current_user.user_id, client_ip, path_id, "hidden_path_not_allowed")
            raise NotFoundError("目录不存在")

        files = self.repository.list_active_by_path_id(path_id, include_hidden=include_hidden)
        self.audit_service.record(
            user_id=current_user.user_id,
            action_type="list_files",
            target_type="file_path",
            target_id=path_id,
            result="success",
            detail={"count": len(files), "show_hidden": include_hidden},
            client_ip=client_ip,
        )
        self.db.commit()
        self.logger.info(
            "文件列表读取完成",
            extra={
                "action": "list_files",
                "target_type": "file_path",
                "target_id": path_id,
                "result": "success",
                "count": len(files),
            },
        )
        return self._to_list_items(files)

    def get_file_detail(
        self,
        *,
        file_id: str,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> FileDetailResponse:
        """读取文件详情；只返回业务元数据和逻辑路径，不返回加密对象路径。"""

        file_info, parent_path = self._get_visible_file_and_path(
            file_id=file_id,
            show_hidden=show_hidden,
            action_type="get_file_detail",
            current_user=current_user,
            client_ip=client_ip,
        )
        self.audit_service.record(
            user_id=current_user.user_id,
            action_type="get_file_detail",
            target_type="file",
            target_id=file_id,
            result="success",
            detail={"path_id": file_info.path_id},
            client_ip=client_ip,
        )
        self.db.commit()
        self.logger.info(
            "文件详情读取完成",
            extra={"action": "get_file_detail", "target_type": "file", "target_id": file_id, "result": "success"},
        )
        return self._to_detail_response(file_info, parent_path)

    def export_file_content(
        self,
        *,
        file_id: str,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> tuple[FileInfo, Iterator[bytes]]:
        """导出单个文件本体，返回解密后的明文流。"""

        file_info, _parent_path = self._get_visible_file_and_path(
            file_id=file_id,
            show_hidden=show_hidden,
            action_type="export_file",
            current_user=current_user,
            client_ip=client_ip,
        )
        self.repository.mark_accessed(file_info)
        self.audit_service.record(
            user_id=current_user.user_id,
            action_type="export_file",
            target_type="file",
            target_id=file_id,
            result="success",
            detail={"size_bytes": file_info.size_bytes},
            client_ip=client_ip,
        )
        self.db.commit()
        return file_info, self.storage_service.iter_content_chunks(file_info)

    def export_files_content(
        self,
        *,
        payload: FileExportRequest,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> tuple[str, str, int, Iterator[bytes]]:
        """批量导出文件：单文件返回本体，多文件返回 zip 压缩包。"""

        if len(payload.file_ids) == 1:
            file_info, chunks = self.export_file_content(
                file_id=payload.file_ids[0],
                show_hidden=show_hidden,
                current_user=current_user,
                client_ip=client_ip,
            )
            return (
                file_info.original_name,
                file_info.mime_type or "application/octet-stream",
                file_info.size_bytes,
                chunks,
            )

        files: list[FileInfo] = []
        try:
            for file_id in payload.file_ids:
                file_info, _parent_path = self._get_visible_file_and_path(
                    file_id=file_id,
                    show_hidden=show_hidden,
                    action_type="export_files",
                    current_user=current_user,
                    client_ip=client_ip,
                )
                files.append(file_info)

            zip_buffer = BytesIO()
            used_names: set[str] = set()
            with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
                for file_info in files:
                    archive_name = self._unique_export_name(file_info.original_name, used_names)
                    with archive.open(archive_name, mode="w") as zip_entry:
                        for chunk in self.storage_service.iter_content_chunks(file_info):
                            zip_entry.write(chunk)
                    self.repository.mark_accessed(file_info)

            zip_bytes = zip_buffer.getvalue()
            export_name = f"pfmt-export-{now_utc().strftime('%Y%m%d-%H%M%S')}.zip"
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="export_files",
                target_type="file",
                result="success",
                detail={"count": len(files), "size_bytes": len(zip_bytes)},
                client_ip=client_ip,
            )
            self.db.commit()
            return export_name, "application/zip", len(zip_bytes), self._iter_bytes(zip_bytes)
        except Exception:
            self.db.rollback()
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="export_files",
                target_type="file",
                result="failed",
                detail={"count": len(payload.file_ids), "reason": "export_failed"},
                client_ip=client_ip,
            )
            self.db.commit()
            raise

    def update_file_remark(
        self,
        *,
        file_id: str,
        payload: FileUpdateRequest,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> FileDetailResponse:
        """更新文件业务元数据，不修改文件本体和存储对象。"""

        file_info, parent_path = self._get_visible_file_and_path(
            file_id=file_id,
            show_hidden=show_hidden,
            action_type="update_file_remark",
            current_user=current_user,
            client_ip=client_ip,
        )
        remark = self._normalize_optional_text(payload.remark)
        summary_content = self._normalize_optional_text(payload.summary_content)
        original_name = payload.original_name.strip() if payload.original_name is not None else None
        if original_name is not None:
            original_name = self._available_file_name(
                parent_path.path_id,
                original_name,
                exclude_file_id=file_info.file_id,
            )
        self.repository.update_metadata(
            file_info,
            original_name=original_name,
            remark=remark,
            summary_content=summary_content,
            is_hidden=payload.is_hidden,
            user_id=current_user.user_id,
        )
        self.audit_service.record(
            user_id=current_user.user_id,
            action_type="update_file_remark",
            target_type="file",
            target_id=file_id,
            result="success",
            detail={
                "has_remark": remark is not None,
                "has_summary": summary_content is not None,
                "renamed": original_name is not None,
                "is_hidden": file_info.is_hidden,
            },
            client_ip=client_ip,
        )
        self.db.commit()
        self.db.refresh(file_info)
        self.logger.info(
            "文件备注更新完成",
            extra={"action": "update_file_remark", "target_type": "file", "target_id": file_id, "result": "success"},
        )
        return self._to_detail_response(file_info, parent_path)

    def search_files(
        self,
        *,
        query: str,
        show_hidden: bool | None,
        limit: int,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> FileSearchResponse:
        """按元数据搜索文件，不读取加密文件本体内容。"""

        normalized_query = query.strip()
        if not normalized_query:
            return FileSearchResponse(items=[], total=0)
        include_hidden = self._include_hidden_files(current_user=current_user)
        files = self.repository.search_active(
            query=normalized_query,
            include_hidden=include_hidden,
            limit=min(max(limit, 1), 100),
        )
        visible_files = [
            file_info
            for file_info in files
            if self._path_visible_for_file(file_info, include_hidden=include_hidden)
        ]
        self.audit_service.record(
            user_id=current_user.user_id,
            action_type="search_files",
            target_type="file",
            result="success",
            detail={"query_length": len(normalized_query), "count": len(visible_files), "show_hidden": include_hidden},
            client_ip=client_ip,
        )
        self.db.commit()
        items: list[FileDetailResponse] = []
        for file_info in visible_files:
            parent_path = self.path_repository.get_active_by_path_id(file_info.path_id)
            if parent_path is not None:
                items.append(self._to_detail_response(file_info, parent_path))
        return FileSearchResponse(items=items, total=len(items))

    def preview_content(
        self,
        *,
        file_id: str,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> tuple[FileInfo, Iterator[bytes]]:
        """返回图片/PDF预览流；不支持的类型由业务错误处理。"""

        file_info, _parent_path = self._get_visible_file_and_path(
            file_id=file_id,
            show_hidden=show_hidden,
            action_type="preview_file",
            current_user=current_user,
            client_ip=client_ip,
        )
        if file_info.file_type not in {"image", "pdf"}:
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="preview_file",
                target_type="file",
                target_id=file_id,
                result="failed",
                detail={"reason": "unsupported_file_type"},
                client_ip=client_ip,
            )
            self.db.commit()
            raise UnsupportedFileTypeError("当前文件类型暂不支持预览")
        self.repository.mark_accessed(file_info)
        self.audit_service.record(
            user_id=current_user.user_id,
            action_type="preview_file",
            target_type="file",
            target_id=file_id,
            result="success",
            detail={"file_type": file_info.file_type},
            client_ip=client_ip,
        )
        self.db.commit()
        return file_info, self.storage_service.iter_content_chunks(file_info)

    def list_tags(self) -> list[FileTagItem]:
        """读取全部活动标签。"""

        return [self._to_tag_item(tag) for tag in self.tag_repository.list_active()]

    def create_tag(
        self,
        *,
        payload: FileTagCreateRequest,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> FileTagItem:
        """创建标签；同名标签直接复用。"""

        tag_name = payload.tag_name.strip()
        existing = self.tag_repository.get_active_by_name(tag_name)
        if existing is not None:
            return self._to_tag_item(existing)
        tag = FileTag(
            tag_id=new_business_id("tag"),
            tag_name=tag_name,
            tag_color=self._normalize_optional_text(payload.tag_color),
        )
        self.tag_repository.create(tag)
        self.audit_service.record(
            user_id=current_user.user_id,
            action_type="create_tag",
            target_type="file_tag",
            target_id=tag.tag_id,
            result="success",
            client_ip=client_ip,
        )
        self.db.commit()
        self.db.refresh(tag)
        return self._to_tag_item(tag)

    def update_file_tags(
        self,
        *,
        file_id: str,
        payload: FileTagsUpdateRequest,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> FileDetailResponse:
        """替换文件标签集合。"""

        file_info, parent_path = self._get_visible_file_and_path(
            file_id=file_id,
            show_hidden=show_hidden,
            action_type="update_file_tags",
            current_user=current_user,
            client_ip=client_ip,
        )
        tags: list[FileTag] = []
        for tag_name in payload.tag_names:
            existing = self.tag_repository.get_active_by_name(tag_name)
            if existing is None:
                existing = FileTag(tag_id=new_business_id("tag"), tag_name=tag_name)
                self.tag_repository.create(existing)
            tags.append(existing)
        self.tag_repository.replace_file_tags(file_id=file_id, tags=tags)
        self.audit_service.record(
            user_id=current_user.user_id,
            action_type="update_file_tags",
            target_type="file",
            target_id=file_id,
            result="success",
            detail={"count": len(tags)},
            client_ip=client_ip,
        )
        self.db.commit()
        self.db.refresh(file_info)
        return self._to_detail_response(file_info, parent_path)

    def move_file(
        self,
        *,
        file_id: str,
        payload: FileMoveRequest,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> FileDetailResponse:
        """移动文件到新的业务目录，不改变底层存储对象。"""

        file_info, parent_path = self._get_visible_file_and_path(
            file_id=file_id,
            show_hidden=show_hidden,
            action_type="move_file",
            current_user=current_user,
            client_ip=client_ip,
        )
        target_path = self.path_repository.get_active_by_path_id(payload.path_id)
        include_hidden = self._include_hidden_files(current_user=current_user)
        if target_path is None or (target_path.is_hidden and not include_hidden):
            self._record_file_action_failure(
                user_id=current_user.user_id,
                client_ip=client_ip,
                file_id=file_id,
                action_type="move_file",
                reason="target_path_not_found",
            )
            raise NotFoundError("目标目录不存在")

        target_name = self._available_file_name(
            target_path.path_id,
            file_info.original_name,
            exclude_file_id=file_info.file_id,
        )

        original_storage_path = file_info.storage_path
        new_storage_path = original_storage_path
        if target_path.path_id != parent_path.path_id:
            new_storage_path = self.storage_service.move_object(
                source_storage_path=original_storage_path,
                target_parent_storage_path=target_path.storage_path,
                storage_object_name=file_info.storage_object_name,
            )
        self.repository.move_to_path(
            file_info,
            path_id=target_path.path_id,
            original_name=target_name,
            visibility_type="normal",
            user_id=current_user.user_id,
        )
        self.repository.update_storage_path(
            file_info,
            storage_path=new_storage_path,
            user_id=current_user.user_id,
        )
        self.audit_service.record(
            user_id=current_user.user_id,
            action_type="move_file",
            target_type="file",
            target_id=file_id,
            result="success",
            detail={"path_id": target_path.path_id},
            client_ip=client_ip,
        )
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            if new_storage_path != original_storage_path:
                self.storage_service.move_object(
                    source_storage_path=new_storage_path,
                    target_parent_storage_path=parent_path.storage_path,
                    storage_object_name=file_info.storage_object_name,
                )
            raise
        self.db.refresh(file_info)
        self.logger.info(
            "文件移动完成",
            extra={"action": "move_file", "target_type": "file", "target_id": file_id, "result": "success"},
        )
        return self._to_detail_response(file_info, target_path)

    def delete_file(
        self,
        *,
        file_id: str,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> None:
        """软删除文件元数据，并在提交成功后删除本地存储对象。"""

        file_info, _parent_path = self._get_visible_file_and_path(
            file_id=file_id,
            show_hidden=show_hidden,
            action_type="delete_file",
            current_user=current_user,
            client_ip=client_ip,
        )
        storage_path = file_info.storage_path
        self.repository.soft_delete(file_info, user_id=current_user.user_id)
        self.audit_service.record(
            user_id=current_user.user_id,
            action_type="delete_file",
            target_type="file",
            target_id=file_id,
            result="success",
            detail={"path_id": file_info.path_id},
            client_ip=client_ip,
        )
        self.db.commit()
        self.storage_service.delete_object(storage_path)
        self.logger.info(
            "文件删除完成",
            extra={"action": "delete_file", "target_type": "file", "target_id": file_id, "result": "success"},
        )

    def delete_files(
        self,
        *,
        payload: FileBatchDeleteRequest,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> None:
        """批量软删除文件元数据，提交成功后清理本地存储对象。"""

        files_to_delete: list[FileInfo] = []
        try:
            for file_id in payload.file_ids:
                file_info, _parent_path = self._get_visible_file_and_path(
                    file_id=file_id,
                    show_hidden=show_hidden,
                    action_type="delete_files",
                    current_user=current_user,
                    client_ip=client_ip,
                )
                files_to_delete.append(file_info)

            storage_paths = [file_info.storage_path for file_info in files_to_delete]
            for file_info in files_to_delete:
                self.repository.soft_delete(file_info, user_id=current_user.user_id)

            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="delete_files",
                target_type="file",
                result="success",
                detail={
                    "file_ids": payload.file_ids,
                    "count": len(files_to_delete),
                },
                client_ip=client_ip,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="delete_files",
                target_type="file",
                result="failed",
                detail={"reason": "delete_failed", "file_ids": payload.file_ids},
                client_ip=client_ip,
            )
            self.db.commit()
            raise

        for storage_path in storage_paths:
            self.storage_service.delete_object(storage_path)
        self.logger.info(
            "文件批量删除完成",
            extra={"action": "delete_files", "target_type": "file", "result": "success"},
        )

    def _record_failed_upload(self, user_id: str, client_ip: str | None, reason: str) -> None:
        """上传失败时单独写入失败审计，避免吞掉关键安全事件。"""

        self.audit_service.record(
            user_id=user_id,
            action_type="upload_file",
            target_type="file",
            result="failed",
            detail={"reason": reason},
            client_ip=client_ip,
        )
        self.db.commit()

    def _record_failed_list(
        self,
        user_id: str,
        client_ip: str | None,
        path_id: str,
        reason: str,
    ) -> None:
        """文件列表读取失败时记录目录与失败原因，便于排查权限或路径问题。"""

        self.audit_service.record(
            user_id=user_id,
            action_type="list_files",
            target_type="file_path",
            target_id=path_id,
            result="failed",
            detail={"reason": reason},
            client_ip=client_ip,
        )
        self.db.commit()
        self.logger.warning(
            "文件列表读取失败",
            extra={
                "action": "list_files",
                "target_type": "file_path",
                "target_id": path_id,
                "result": "failed",
                "reason": reason,
            },
        )

    def _record_file_action_failure(
        self,
        *,
        user_id: str,
        client_ip: str | None,
        file_id: str,
        action_type: str,
        reason: str,
    ) -> None:
        """文件详情类操作失败时记录统一审计和业务日志。"""

        self.audit_service.record(
            user_id=user_id,
            action_type=action_type,
            target_type="file",
            target_id=file_id,
            result="failed",
            detail={"reason": reason},
            client_ip=client_ip,
        )
        self.db.commit()
        self.logger.warning(
            "文件操作失败",
            extra={
                "action": action_type,
                "target_type": "file",
                "target_id": file_id,
                "result": "failed",
                "reason": reason,
            },
        )

    def _include_hidden_files(self, *, current_user: UserAccount) -> bool:
        """依据隐藏功能开关和当前会话状态决定是否返回隐藏文件。"""

        hidden_feature_enabled = self.setting_service.get_bool("hidden.feature_enabled", True)
        session_enabled = bool(getattr(current_user, "_pfmt_show_hidden_enabled", False))
        return hidden_feature_enabled and session_enabled

    def _get_visible_file_and_path(
        self,
        *,
        file_id: str,
        show_hidden: bool | None,
        action_type: str,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> tuple[FileInfo, FilePath]:
        """查询文件并按隐藏规则校验可见性，避免详情或读取接口绕过列表过滤。"""

        file_info = self.repository.get_active_by_file_id(file_id)
        if file_info is None:
            self._record_file_action_failure(
                user_id=current_user.user_id,
                client_ip=client_ip,
                file_id=file_id,
                action_type=action_type,
                reason="file_not_found",
            )
            raise NotFoundError("文件不存在")

        parent_path = self.path_repository.get_active_by_path_id(file_info.path_id)
        if parent_path is None:
            self._record_file_action_failure(
                user_id=current_user.user_id,
                client_ip=client_ip,
                file_id=file_id,
                action_type=action_type,
                reason="path_not_found",
            )
            raise NotFoundError("文件不存在")

        include_hidden = self._include_hidden_files(current_user=current_user)
        if (file_info.is_hidden or parent_path.is_hidden) and not include_hidden:
            self._record_file_action_failure(
                user_id=current_user.user_id,
                client_ip=client_ip,
                file_id=file_id,
                action_type=action_type,
                reason="hidden_file_not_allowed",
            )
            raise NotFoundError("文件不存在")

        return file_info, parent_path

    def _decode_preview_token(self, *, token: str, file_id: str, purpose: str = "video_preview") -> dict[str, Any]:
        try:
            payload = jwt.decode(token, self.settings.effective_jwt_secret, algorithms=[self.settings.jwt_algorithm])
        except jwt.PyJWTError as exc:
            raise AuthenticationError("预览链接无效或已过期") from exc

        if (
            payload.get("purpose") != purpose
            or payload.get("fid") != file_id
            or not payload.get("sub")
            or not payload.get("sid")
        ):
            raise AuthenticationError("预览链接无效或已过期")
        return payload

    def _get_visible_file_for_token(
        self,
        *,
        file_id: str,
        include_hidden: bool,
        user_id: str,
        client_ip: str | None,
        action_type: str,
    ) -> tuple[FileInfo, FilePath]:
        file_info = self.repository.get_active_by_file_id(file_id)
        if file_info is None:
            self._record_file_action_failure(
                user_id=user_id,
                client_ip=client_ip,
                file_id=file_id,
                action_type=action_type,
                reason="file_not_found",
            )
            raise NotFoundError("文件不存在")

        parent_path = self.path_repository.get_active_by_path_id(file_info.path_id)
        if parent_path is None:
            self._record_file_action_failure(
                user_id=user_id,
                client_ip=client_ip,
                file_id=file_id,
                action_type=action_type,
                reason="path_not_found",
            )
            raise NotFoundError("文件不存在")

        if (file_info.is_hidden or parent_path.is_hidden) and not include_hidden:
            self._record_file_action_failure(
                user_id=user_id,
                client_ip=client_ip,
                file_id=file_id,
                action_type=action_type,
                reason="hidden_file_not_allowed",
            )
            raise NotFoundError("文件不存在")

        return file_info, parent_path

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        """空白字符串按未填写处理，非空内容保留换行。"""

        if value is None:
            return None
        return value if value.strip() else None

    def _read_text_content(self, file_info: FileInfo) -> str:
        content_bytes = bytearray()
        for chunk in self.storage_service.iter_content_chunks(file_info):
            content_bytes.extend(chunk)

        try:
            return bytes(content_bytes).decode("utf-8-sig")
        except UnicodeDecodeError:
            return bytes(content_bytes).decode("utf-8", errors="replace")

    def _convert_document_content(self, content: str, source_format: str, target_format: str) -> str:
        if source_format == target_format:
            return content
        if target_format == "plain_text":
            return self._document_to_plain_text(content, source_format)
        if target_format == "html":
            return self._render_document_html(content, source_format) or ""
        if target_format == "markdown":
            if source_format == "html":
                return self._document_to_plain_text(content, source_format)
            return content
        raise UnsupportedFileTypeError("不支持的目标格式")

    def _merge_document_contents(
        self,
        source_files: list[tuple[FileInfo, str, str]],
        target_format: str,
    ) -> str:
        sections: list[str] = []
        for file_info, source_format, content in source_files:
            converted_content = self._convert_document_content(content, source_format, target_format).strip()
            if target_format == "html":
                sections.append(
                    f'<section data-source-file-id="{escape(file_info.file_id)}">'
                    f"<h1>{escape(file_info.original_name)}</h1>\n{converted_content}</section>"
                )
            elif target_format == "markdown":
                sections.append(f"# {file_info.original_name}\n\n{converted_content}")
            else:
                sections.append(f"{file_info.original_name}\n\n{converted_content}")
        separator = "\n\n---\n\n" if target_format == "markdown" else "\n\n"
        return separator.join(sections).strip() + "\n"

    def _create_generated_document_file(
        self,
        *,
        path_id: str,
        target_name: str,
        target_format: str,
        content: str,
        current_user: UserAccount,
        source_file: FileInfo | None = None,
        is_hidden: bool | None = None,
    ) -> FileInfo:
        target_file_id = new_business_id("file")
        should_encrypt = self.setting_service.get_bool("storage.encryption_enabled", True)
        parent_path = self.path_repository.get_active_by_path_id(path_id)
        if parent_path is None:
            raise NotFoundError("目录不存在")
        target_name = self._available_file_name(path_id, target_name)
        stored_object = self.storage_service.save_bytes(
            content=content.encode("utf-8"),
            file_id=target_file_id,
            encryption_enabled=should_encrypt,
            parent_storage_path=parent_path.storage_path,
        )
        return self.repository.create(
            FileInfo(
                file_id=target_file_id,
                path_id=path_id,
                original_name=target_name,
                storage_object_name=stored_object.storage_object_name,
                storage_path=stored_object.storage_path,
                storage_provider="local",
                mime_type=document_format_mime_type(target_format),
                file_ext=document_format_extension(target_format),
                file_type="text",
                size_bytes=stored_object.size_bytes,
                checksum_sha256=stored_object.checksum_sha256,
                encryption_enabled=should_encrypt,
                key_wrap_version=stored_object.key_wrap_version,
                key_id=stored_object.key_id,
                remark=source_file.remark if source_file else None,
                summary_content=source_file.summary_content if source_file else None,
                summary_source=source_file.summary_source if source_file else None,
                summary_updated_at=source_file.summary_updated_at if source_file else None,
                is_hidden=is_hidden if is_hidden is not None else (source_file.is_hidden if source_file else False),
                visibility_type="normal",
                created_by=current_user.user_id,
                updated_by=current_user.user_id,
            )
        )

    @staticmethod
    def _document_to_plain_text(content: str, source_format: str) -> str:
        if source_format == "html":
            parser = _PlainTextExtractor()
            parser.feed(content)
            return parser.text()
        if source_format == "markdown":
            text = re.sub(r"```.*?```", "", content, flags=re.S)
            text = re.sub(r"`([^`]*)`", r"\1", text)
            text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
            text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
            text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
            text = re.sub(r"[*_~>#-]+", "", text)
            return "\n".join(line.rstrip() for line in text.splitlines()).strip()
        return content

    @staticmethod
    def _is_safe_embed_src(src: str) -> bool:
        """文档内嵌图片引用仅放行系统内部文件路径或 http(s) 链接。"""

        lowered = src.lower()
        if lowered.startswith("data:") or lowered.startswith("javascript:"):
            return False
        if lowered.startswith("/api/files/"):
            return True
        return lowered.startswith("http://") or lowered.startswith("https://")

    @staticmethod
    def _render_document_html(content: str, document_format: str) -> str | None:
        if document_format == "html":
            return content
        if document_format == "plain_text":
            paragraphs = escape(content).splitlines() or [""]
            return "\n".join(f"<p>{line}</p>" if line else "<p><br></p>" for line in paragraphs)
        if document_format == "markdown":
            html_lines: list[str] = []
            in_list = False
            for raw_line in content.splitlines():
                line = raw_line.strip()
                if not line:
                    if in_list:
                        html_lines.append("</ul>")
                        in_list = False
                    continue
                image_match = re.match(r"^!\[([^\]]*)\]\(([^)\s]+)\)$", line)
                if image_match:
                    if in_list:
                        html_lines.append("</ul>")
                        in_list = False
                    src = image_match.group(2)
                    if FileService._is_safe_embed_src(src):
                        html_lines.append(f'<p><img src="{src}" alt="{escape(image_match.group(1))}"></p>')
                    else:
                        html_lines.append(f"<p>{escape(line)}</p>")
                    continue
                heading = re.match(r"^(#{1,6})\s+(.+)$", line)
                if heading:
                    if in_list:
                        html_lines.append("</ul>")
                        in_list = False
                    level = len(heading.group(1))
                    html_lines.append(f"<h{level}>{escape(heading.group(2))}</h{level}>")
                    continue
                list_item = re.match(r"^[-*]\s+(.+)$", line)
                if list_item:
                    if not in_list:
                        html_lines.append("<ul>")
                        in_list = True
                    html_lines.append(f"<li>{escape(list_item.group(1))}</li>")
                    continue
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<p>{escape(line)}</p>")
            if in_list:
                html_lines.append("</ul>")
            return "\n".join(html_lines)
        return None

    @staticmethod
    def _default_converted_name(original_name: str, target_format: str) -> str:
        stem = Path(original_name).stem or "document"
        return f"{stem}{document_format_extension(target_format)}"

    @staticmethod
    def _unique_export_name(original_name: str, used_names: set[str]) -> str:
        safe_name = original_name.replace("\\", "_").replace("/", "_").strip() or "file"
        candidate = safe_name
        index = 1
        path = Path(safe_name)
        while candidate in used_names:
            candidate = FileService._numbered_file_name(path, index)
            index += 1
        used_names.add(candidate)
        return candidate

    def _available_file_name(self, path_id: str, original_name: str, *, exclude_file_id: str | None = None) -> str:
        """生成同目录内可用展示文件名，避免向用户返回重名冲突。"""

        safe_name = Path(original_name).name.strip() or "unnamed"
        candidate = safe_name
        index = 1
        path = Path(safe_name)
        while (
            self.repository.get_active_by_name(
                path_id=path_id,
                original_name=candidate,
                exclude_file_id=exclude_file_id,
            )
            is not None
        ):
            candidate = self._numbered_file_name(path, index)
            index += 1
        return candidate

    @staticmethod
    def _numbered_file_name(path: Path, index: int) -> str:
        return f"{path.stem}({index}){path.suffix}"

    @staticmethod
    def _iter_bytes(content: bytes) -> Iterator[bytes]:
        chunk_size = 64 * 1024
        for start in range(0, len(content), chunk_size):
            yield content[start : start + chunk_size]

    def _path_visible_for_file(self, file_info: FileInfo, *, include_hidden: bool) -> bool:
        parent_path = self.path_repository.get_active_by_path_id(file_info.path_id)
        if parent_path is None:
            return False
        return include_hidden or not parent_path.is_hidden

    @staticmethod
    def _logical_path(parent_path: FilePath, file_info: FileInfo) -> str:
        """拼接用户可理解的业务逻辑路径。"""

        if parent_path.full_path == "/":
            return f"/{file_info.original_name}"
        return f"{parent_path.full_path.rstrip('/')}/{file_info.original_name}"

    def _to_list_items(self, files: list[FileInfo]) -> list[FileListItem]:
        tags_by_file_id = self.tag_repository.get_active_by_file_ids([file_info.file_id for file_info in files])
        return [self._to_list_item(file_info, tags_by_file_id.get(file_info.file_id, [])) for file_info in files]

    def _to_list_item(self, file_info: FileInfo, tags: list[FileTag] | None = None) -> FileListItem:
        """将文件模型转换为列表响应，刻意不返回底层存储对象名。"""

        return FileListItem(
            file_id=file_info.file_id,
            path_id=file_info.path_id,
            original_name=file_info.original_name,
            mime_type=file_info.mime_type,
            file_ext=file_info.file_ext,
            file_type=file_info.file_type,
            size_bytes=file_info.size_bytes,
            encryption_enabled=file_info.encryption_enabled,
            is_hidden=file_info.is_hidden,
            status=file_info.status,
            remark=file_info.remark,
            summary_content=file_info.summary_content,
            tags=[self._to_tag_item(tag) for tag in (tags or self.tag_repository.get_active_by_file_id(file_info.file_id))],
            created_at=file_info.created_at or now_utc(),
            updated_at=file_info.updated_at or now_utc(),
            last_accessed_at=file_info.last_accessed_at,
        )

    def _to_detail_response(self, file_info: FileInfo, parent_path: FilePath) -> FileDetailResponse:
        """将文件模型转换为详情响应，补充业务逻辑路径。"""

        return FileDetailResponse(
            **self._to_list_item(file_info).model_dump(),
            logical_path=self._logical_path(parent_path, file_info),
            checksum_sha256=file_info.checksum_sha256,
        )

    @staticmethod
    def _to_tag_item(tag: FileTag) -> FileTagItem:
        return FileTagItem(tag_id=tag.tag_id, tag_name=tag.tag_name, tag_color=tag.tag_color)

    @staticmethod
    def _to_upload_response(file_info: FileInfo) -> FileUploadResponse:
        """将文件元数据模型转换为上传响应。"""

        return FileUploadResponse(
            file_id=file_info.file_id,
            path_id=file_info.path_id,
            original_name=file_info.original_name,
            storage_provider=file_info.storage_provider,
            mime_type=file_info.mime_type,
            file_ext=file_info.file_ext,
            file_type=file_info.file_type,
            size_bytes=file_info.size_bytes,
            checksum_sha256=file_info.checksum_sha256,
            encryption_enabled=file_info.encryption_enabled,
            key_wrap_version=file_info.key_wrap_version,
            is_hidden=file_info.is_hidden,
            status=file_info.status,
            created_at=file_info.created_at or now_utc(),
            updated_at=file_info.updated_at or now_utc(),
            last_accessed_at=file_info.last_accessed_at,
        )
