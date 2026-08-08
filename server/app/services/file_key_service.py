import base64
import hashlib
import logging
import secrets
import shutil
import threading
from dataclasses import dataclass

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_session_factory
from app.core.exceptions import AppError
from app.core.security import now_utc
from app.models.file import FileInfo
from app.models.system import FileKeyVersion
from app.repositories.file_key_repository import FileKeyRepository
from app.repositories.setting_repository import SettingRepository
from app.utils.crypto import normalize_key_material


_rotation_running = False
_rotation_lock = threading.Lock()


@dataclass(frozen=True)
class ResolvedFileKey:
    key_id: str
    key: bytes


@dataclass(frozen=True)
class FileEncryptionStatus:
    encryption_enabled: bool
    key_configured: bool
    active_key_id: str | None
    active_key_status: str | None
    pending_rotation_count: int


class FileKeyService:
    """管理数据库中的文件加密 key。"""

    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.repository = FileKeyRepository(db)

    def status(self) -> FileEncryptionStatus:
        active = self.repository.get_active()
        return FileEncryptionStatus(
            encryption_enabled=self._system_encryption_enabled(),
            key_configured=active is not None,
            active_key_id=active.key_id if active is not None else None,
            active_key_status=active.status if active is not None else None,
            pending_rotation_count=self.pending_rotation_count(active.key_id if active is not None else None),
        )

    def enable(self, key_material: str) -> FileKeyVersion:
        key_version = self.create_and_activate_key(key_material)
        self._set_system_encryption_enabled(True)
        self._refresh_active_status(key_version)
        self.db.commit()
        self.db.refresh(key_version)
        return key_version

    def rotate(self, key_material: str) -> FileKeyVersion:
        key_version = self.create_and_activate_key(key_material)
        self._refresh_active_status(key_version)
        self.db.commit()
        self.db.refresh(key_version)
        return key_version

    def disable_default_encryption(self) -> None:
        self._set_system_encryption_enabled(False)
        self.db.commit()

    def create_and_activate_key(self, key_material: str) -> FileKeyVersion:
        normalized_material = key_material.strip()
        if not normalized_material:
            raise AppError("文件加密密钥不能为空", error_code="file_encryption_key_required")

        key_bytes = normalize_key_material(normalized_material)
        key_hash = self._fingerprint(key_bytes)
        key_version = FileKeyVersion(
            key_id=self._new_key_id(),
            key_material=normalized_material,
            key_hash=key_hash,
            status="active_rotating",
            is_active=False,
        )
        self.repository.create(key_version)
        self.repository.activate(key_version)
        return key_version

    def active_key(self) -> ResolvedFileKey:
        key_version = self.repository.get_active()
        if key_version is None:
            raise AppError(
                "请先配置文件加密密钥",
                error_code="file_encryption_key_required",
            )
        return ResolvedFileKey(key_id=key_version.key_id, key=normalize_key_material(key_version.key_material))

    def key_for_file(self, file_info: FileInfo) -> ResolvedFileKey:
        if not file_info.key_id:
            raise AppError("加密文件缺少 key_id", error_code="file_encryption_key_missing")
        key_version = self.repository.get_by_key_id(file_info.key_id)
        if key_version is None:
            raise AppError(f"文件密钥不存在: {file_info.key_id}", error_code="file_encryption_key_missing")
        return ResolvedFileKey(key_id=key_version.key_id, key=normalize_key_material(key_version.key_material))

    def pending_rotation_count(self, active_key_id: str | None = None) -> int:
        if not active_key_id:
            return 0
        return self.db.execute(
            select(func.count(FileInfo.id)).where(
                FileInfo.status == "active",
                FileInfo.encryption_enabled.is_(True),
                or_(FileInfo.key_id.is_(None), FileInfo.key_id != active_key_id),
            )
        ).scalar_one()

    def refresh_active_status(self) -> None:
        active = self.repository.get_active()
        if active is not None:
            self._refresh_active_status(active)

    def _refresh_active_status(self, key_version: FileKeyVersion) -> None:
        if self.pending_rotation_count(key_version.key_id) == 0:
            self.repository.mark_completed(key_version)
        else:
            key_version.status = "active_rotating"

    def _system_encryption_enabled(self) -> bool:
        setting = SettingRepository(self.db).get_by_key("storage.encryption_enabled")
        if setting is None or setting.setting_value is None:
            return True
        return setting.setting_value.strip().lower() in {"1", "true", "yes", "on"}

    def _set_system_encryption_enabled(self, enabled: bool) -> None:
        from app.models.system import SystemSetting

        SettingRepository(self.db).upsert(
            SystemSetting(
                setting_key="storage.encryption_enabled",
                setting_value="true" if enabled else "false",
                value_type="boolean",
                group_name="storage",
                description="是否默认启用文件本体加密",
                is_public=True,
            )
        )

    @staticmethod
    def _fingerprint(key: bytes) -> str:
        return hashlib.sha256(key).hexdigest()

    @staticmethod
    def _new_key_id() -> str:
        token = base64.urlsafe_b64encode(secrets.token_bytes(6)).decode("ascii").rstrip("=")
        return f"key_{now_utc().strftime('%Y%m%d%H%M%S')}_{token}"


class FileKeyRotationService:
    """后台把旧 key_id 的文件逐步重写到当前 active key。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger("pfmt.file_key_rotation")

    def start_once(self) -> None:
        global _rotation_running
        with _rotation_lock:
            if _rotation_running:
                return
            _rotation_running = True
        thread = threading.Thread(target=self._run_and_release, name="pfmt-file-key-rotation", daemon=True)
        thread.start()

    def _run_and_release(self) -> None:
        global _rotation_running
        try:
            self.rotate_pending_files()
        finally:
            with _rotation_lock:
                _rotation_running = False

    def rotate_pending_files(self) -> None:
        self._clear_rotation_tmp()
        db = get_session_factory(self.settings)()
        try:
            key_service = FileKeyService(db, self.settings)
            active = key_service.active_key()
            while True:
                pending = db.execute(
                    select(FileInfo)
                    .where(
                        FileInfo.status == "active",
                        FileInfo.encryption_enabled.is_(True),
                        or_(FileInfo.key_id.is_(None), FileInfo.key_id != active.key_id),
                    )
                    .limit(20)
                ).scalars().all()
                if not pending:
                    key_service.refresh_active_status()
                    db.commit()
                    break
                for file_info in pending:
                    self._rotate_one(db, file_info, active.key_id)
        except AppError:
            self.logger.info("没有可用文件加密 key，跳过文件密钥轮转")
        except Exception:
            self.logger.exception("文件密钥轮转任务失败")
        finally:
            db.close()

    def _rotate_one(self, db: Session, file_info: FileInfo, active_key_id: str) -> None:
        from app.services.storage_service import StorageService

        old_storage_path = file_info.storage_path
        old_object_name = file_info.storage_object_name
        old_key_id = file_info.key_id
        try:
            storage = StorageService(self.settings, db=db)
            stored = storage.reencrypt_file_to_temp_object(file_info=file_info, target_key_id=active_key_id)
            updated = db.execute(
                update(FileInfo)
                .where(
                    FileInfo.file_id == file_info.file_id,
                    FileInfo.storage_path == old_storage_path,
                    FileInfo.key_id == old_key_id,
                )
                .values(
                    storage_object_name=stored.storage_object_name,
                    storage_path=stored.storage_path,
                    key_id=stored.key_id,
                    key_wrap_version=stored.key_wrap_version,
                    updated_at=now_utc(),
                )
            ).rowcount
            if updated != 1:
                db.rollback()
                storage.delete_object(stored.storage_path)
                self.logger.info("文件密钥轮转跳过并发变更文件", extra={"file_id": file_info.file_id})
                return
            db.commit()
            storage.delete_object(old_storage_path)
        except Exception:
            db.rollback()
            self.logger.exception(
                "文件密钥轮转单文件失败",
                extra={"file_id": file_info.file_id, "key_id": old_key_id, "object_name": old_object_name},
            )

    def _clear_rotation_tmp(self) -> None:
        temp_root = self.settings.storage_root_path / ".rotation_tmp"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)
