import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_session_factory
from app.models.file import FileInfo, FilePath
from app.services.storage_service import StorageService


class StorageIntegrityService:
    """启动时校验 SQLite 元数据和本地存储树的一致性。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.storage_service = StorageService(settings)
        self.logger = logging.getLogger("pfmt.storage")

    def verify_storage_root(self) -> None:
        """在 SQLite 初始化前确认存储根路径存在。"""

        try:
            self.storage_service.ensure_storage_root_available()
        except RuntimeError:
            self.logger.critical("文件存储根路径不存在，已阻断启动", exc_info=True)
            raise

    def verify_inventory(self) -> None:
        """数据库初始化后检查 active 清单；缺失只告警，不阻断启动。"""

        self.storage_service.ensure_data_root()
        db = get_session_factory(self.settings)()
        try:
            self._verify_paths(db)
            self._verify_files(db)
        finally:
            db.close()

    def _verify_paths(self, db: Session) -> None:
        missing: list[str] = []
        invalid: list[str] = []
        paths = db.execute(select(FilePath).where(FilePath.status == "active")).scalars().all()
        for path in paths:
            if path.path_id == "root":
                if path.storage_path != self.storage_service.root_storage_path():
                    invalid.append(path.path_id)
                continue
            if not path.storage_path:
                invalid.append(path.path_id)
                continue
            if not (self.settings.storage_root_path / path.storage_path).is_dir():
                missing.append(path.path_id)

        if invalid:
            self.logger.warning("目录存储元数据不完整", extra={"path_ids": invalid[:20], "count": len(invalid)})
        if missing:
            self.logger.warning("SQLite 清单中的目录缺失真实存储路径", extra={"path_ids": missing[:20], "count": len(missing)})

    def _verify_files(self, db: Session) -> None:
        missing: list[str] = []
        invalid: list[str] = []
        files = db.execute(select(FileInfo).where(FileInfo.status == "active")).scalars().all()
        for file_info in files:
            if not file_info.storage_path:
                invalid.append(file_info.file_id)
                continue
            if not (self.settings.storage_root_path / file_info.storage_path).is_file():
                missing.append(file_info.file_id)

        if invalid:
            self.logger.warning("文件存储元数据不完整", extra={"file_ids": invalid[:20], "count": len(invalid)})
        if missing:
            self.logger.warning("SQLite 清单中的文件缺失真实存储对象", extra={"file_ids": missing[:20], "count": len(missing)})
