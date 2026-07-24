from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import now_utc
from app.models.file import FileInfo


class FileRepository:
    """封装文件元数据查询与写入。"""

    def __init__(self, db: Session):
        self.db = db

    def create(self, file_info: FileInfo) -> FileInfo:
        """新增文件元数据。"""

        self.db.add(file_info)
        return file_info

    def get_active_by_file_id(self, file_id: str) -> FileInfo | None:
        """按业务文件 ID 查询未删除文件。"""

        stmt = select(FileInfo).where(FileInfo.file_id == file_id, FileInfo.status == "active")
        return self.db.execute(stmt).scalar_one_or_none()

    def list_active_by_path_id(self, path_id: str, *, include_hidden: bool) -> list[FileInfo]:
        """按目录 ID 查询文件列表，默认过滤隐藏文件。"""

        stmt = select(FileInfo).where(FileInfo.path_id == path_id, FileInfo.status == "active")
        if not include_hidden:
            stmt = stmt.where(FileInfo.is_hidden.is_(False))
        stmt = stmt.order_by(FileInfo.updated_at.desc(), FileInfo.id.desc())
        return list(self.db.execute(stmt).scalars().all())

    def list_active_by_path_ids(self, path_ids: Sequence[str]) -> list[FileInfo]:
        """查询多个目录下的未删除文件，用于目录级删除。"""

        if not path_ids:
            return []

        stmt = select(FileInfo).where(FileInfo.path_id.in_(path_ids), FileInfo.status == "active")
        return list(self.db.execute(stmt).scalars().all())

    def mark_accessed(self, file_info: FileInfo) -> None:
        """更新文件最近访问时间。"""

        file_info.last_accessed_at = now_utc()
        file_info.updated_at = now_utc()

    def update_remark(self, file_info: FileInfo, *, remark: str | None, user_id: str) -> None:
        """更新文件备注和更新人。"""

        file_info.remark = remark
        file_info.updated_by = user_id
        file_info.updated_at = now_utc()

    def move_to_path(self, file_info: FileInfo, *, path_id: str, visibility_type: str, user_id: str) -> None:
        """移动文件到新的业务目录。"""

        file_info.path_id = path_id
        file_info.visibility_type = visibility_type
        file_info.updated_by = user_id
        file_info.updated_at = now_utc()

    def soft_delete(self, file_info: FileInfo, *, user_id: str) -> None:
        """软删除文件元数据。"""

        file_info.status = "deleted"
        file_info.updated_by = user_id
        file_info.updated_at = now_utc()
