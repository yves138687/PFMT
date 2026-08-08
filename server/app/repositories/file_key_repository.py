from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import now_utc
from app.models.system import FileKeyVersion


class FileKeyRepository:
    """文件加密密钥版本仓储。"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_key_id(self, key_id: str) -> FileKeyVersion | None:
        stmt = select(FileKeyVersion).where(FileKeyVersion.key_id == key_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_active(self) -> FileKeyVersion | None:
        stmt = select(FileKeyVersion).where(
            FileKeyVersion.is_active.is_(True),
            FileKeyVersion.status.in_(("active_rotating", "active_completed")),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(self) -> list[FileKeyVersion]:
        stmt = select(FileKeyVersion).order_by(FileKeyVersion.created_at.asc(), FileKeyVersion.id.asc())
        return list(self.db.execute(stmt).scalars().all())

    def create(self, key_version: FileKeyVersion) -> FileKeyVersion:
        self.db.add(key_version)
        return key_version

    def activate(self, key_version: FileKeyVersion) -> None:
        for item in self.list_all():
            if item.key_id == key_version.key_id:
                continue
            if item.is_active:
                item.is_active = False
                item.status = "expired"
                item.expired_at = now_utc()
        key_version.is_active = True
        key_version.status = "active_rotating"
        key_version.activated_at = now_utc()

    def mark_completed(self, key_version: FileKeyVersion) -> None:
        if key_version.is_active:
            key_version.status = "active_completed"
            key_version.completed_at = now_utc()

    def expire(self, key_version: FileKeyVersion) -> None:
        key_version.is_active = False
        key_version.status = "expired"
        key_version.expired_at = now_utc()

    def delete(self, key_version: FileKeyVersion) -> None:
        self.db.delete(key_version)
