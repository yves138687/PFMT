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

    def mark_accessed(self, file_info: FileInfo) -> None:
        """更新文件最近访问时间。"""

        file_info.last_accessed_at = now_utc()
        file_info.updated_at = now_utc()
