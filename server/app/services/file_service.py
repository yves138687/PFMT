import logging
from datetime import timedelta, timezone
from pathlib import Path
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import jwt
from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, PayloadTooLargeError, UnsupportedFileTypeError
from app.core.security import now_utc
from app.models.file import FileInfo, FilePath, FileTag
from app.models.user import UserAccount
from app.repositories.file_repository import FileRepository, FileTagRepository
from app.repositories.path_repository import PathRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.file import (
    FileDetailResponse,
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
from app.utils.file_type import detect_file_type, is_markdown_file, is_text_file, normalize_extension
from app.utils.ids import new_business_id


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

    async def upload_file(
        self,
        *,
        upload_file: UploadFile,
        path_id: str,
        current_user: UserAccount,
        client_ip: str | None,
        encryption_enabled: bool | None,
        is_hidden: bool,
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
        file_type = detect_file_type(file_ext, mime_type)
        should_encrypt = (
            self.setting_service.get_bool("storage.encryption_enabled", True)
            if encryption_enabled is None
            else encryption_enabled
        )

        stored_object: StoredObject | None = None
        try:
            stored_object = await self.storage_service.save_upload_file(
                upload_file=upload_file,
                file_id=file_id,
                encryption_enabled=should_encrypt,
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
            content = self._read_text_content(file_info, too_large_message="Markdown 文件超过当前读取上限")
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
            content = self._read_text_content(file_info, too_large_message="文本文件超过当前读取上限")
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

        file_info, _parent_path = self._get_visible_file_and_path(
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

        self.repository.move_to_path(
            file_info,
            path_id=target_path.path_id,
            visibility_type="normal",
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
        self.db.commit()
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

    def _decode_preview_token(self, *, token: str, file_id: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(token, self.settings.effective_jwt_secret, algorithms=[self.settings.jwt_algorithm])
        except jwt.PyJWTError as exc:
            raise AuthenticationError("视频预览链接无效或已过期") from exc

        if (
            payload.get("purpose") != "video_preview"
            or payload.get("fid") != file_id
            or not payload.get("sub")
            or not payload.get("sid")
        ):
            raise AuthenticationError("视频预览链接无效或已过期")
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

    def _read_text_content(self, file_info: FileInfo, *, too_large_message: str) -> str:
        if file_info.size_bytes > self.settings.markdown_read_max_bytes:
            raise PayloadTooLargeError(too_large_message)

        content_bytes = bytearray()
        for chunk in self.storage_service.iter_content_chunks(file_info):
            content_bytes.extend(chunk)
            if len(content_bytes) > self.settings.markdown_read_max_bytes:
                raise PayloadTooLargeError(too_large_message)

        try:
            return bytes(content_bytes).decode("utf-8-sig")
        except UnicodeDecodeError:
            return bytes(content_bytes).decode("utf-8", errors="replace")

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
            visibility_type=file_info.visibility_type,
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
            visibility_type=file_info.visibility_type,
            status=file_info.status,
            created_at=file_info.created_at or now_utc(),
            updated_at=file_info.updated_at or now_utc(),
            last_accessed_at=file_info.last_accessed_at,
        )
