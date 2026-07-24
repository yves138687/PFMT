import logging
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, PayloadTooLargeError, UnsupportedFileTypeError
from app.core.security import now_utc
from app.models.file import FileInfo
from app.models.user import UserAccount
from app.repositories.file_repository import FileRepository
from app.repositories.path_repository import PathRepository
from app.schemas.file import FileUploadResponse, MarkdownReadResponse
from app.services.audit_service import AuditService
from app.services.setting_service import SettingService
from app.services.storage_service import StorageService, StoredObject
from app.utils.file_type import detect_file_type, is_markdown_file, normalize_extension
from app.utils.ids import new_business_id


class FileService:
    """文件服务，编排上传、加密存储、元数据和 Markdown 读取。"""

    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.repository = FileRepository(db)
        self.path_repository = PathRepository(db)
        self.setting_service = SettingService(db)
        self.audit_service = AuditService(db)
        self.storage_service = StorageService(settings)
        self.logger = logging.getLogger("pfmt.business")

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
                visibility_type="private" if parent_path.path_type == "private" or is_hidden else "normal",
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
        current_user: UserAccount,
        client_ip: str | None,
    ) -> MarkdownReadResponse:
        """读取 Markdown 文件，必要时按加密 envelope 分块解密。"""

        file_info = self.repository.get_active_by_file_id(file_id)
        if file_info is None:
            raise NotFoundError("文件不存在")

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

        hidden_feature_enabled = self.setting_service.get_bool("hidden.feature_enabled", True)
        show_hidden_default = self.setting_service.get_bool("hidden.show_hidden_default", False)
        if file_info.is_hidden and hidden_feature_enabled and not show_hidden_default:
            self.audit_service.record(
                user_id=current_user.user_id,
                action_type="read_markdown",
                target_type="file",
                target_id=file_id,
                result="failed",
                detail={"reason": "hidden_file_not_allowed"},
                client_ip=client_ip,
            )
            self.db.commit()
            raise NotFoundError("文件不存在")

        if file_info.size_bytes > self.settings.markdown_read_max_bytes:
            raise PayloadTooLargeError("Markdown 文件超过当前读取上限")

        try:
            content_bytes = bytearray()
            for chunk in self.storage_service.iter_content_chunks(file_info):
                content_bytes.extend(chunk)
                if len(content_bytes) > self.settings.markdown_read_max_bytes:
                    raise PayloadTooLargeError("Markdown 文件超过当前读取上限")

            try:
                content = bytes(content_bytes).decode("utf-8-sig")
            except UnicodeDecodeError:
                content = bytes(content_bytes).decode("utf-8", errors="replace")

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

    def list_files(
        self,
        *,
        path_id: str,
        show_hidden: bool | None,
        current_user: UserAccount,
        client_ip: str | None,
    ) -> list[FileUploadResponse]:
        """读取指定目录下的文件元数据列表，前端用它展示文件列表和逻辑地址。"""

        include_hidden = self._include_hidden_files(show_hidden)
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
        return [self._to_upload_response(file_info) for file_info in files]

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

    def _include_hidden_files(self, show_hidden: bool | None) -> bool:
        """依据隐藏功能开关和请求参数决定是否返回隐藏文件。"""

        hidden_feature_enabled = self.setting_service.get_bool("hidden.feature_enabled", True)
        if not hidden_feature_enabled:
            return True
        if show_hidden is not None:
            return show_hidden
        return self.setting_service.get_bool("hidden.show_hidden_default", False)

    @staticmethod
    def _to_upload_response(file_info: FileInfo) -> FileUploadResponse:
        """将文件元数据模型转换为上传响应。"""

        return FileUploadResponse(
            file_id=file_info.file_id,
            path_id=file_info.path_id,
            original_name=file_info.original_name,
            storage_object_name=file_info.storage_object_name,
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
