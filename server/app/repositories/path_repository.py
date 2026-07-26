from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.file import FilePath


class PathRepository:
    """封装目录树节点查询和创建。"""

    def __init__(self, db: Session):
        """绑定当前请求事务使用的数据库会话。"""

        self.db = db

    def get_by_path_id(self, path_id: str) -> FilePath | None:
        """按业务目录 ID 查询目录。"""

        stmt = select(FilePath).where(FilePath.path_id == path_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_active_by_path_id(self, path_id: str) -> FilePath | None:
        """查询未删除目录。"""

        stmt = select(FilePath).where(FilePath.path_id == path_id, FilePath.status == "active")
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_full_path(self, full_path: str) -> FilePath | None:
        """按完整路径查询目录，用于防止同级重名。"""

        stmt = select(FilePath).where(FilePath.full_path == full_path)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_active(self, *, include_hidden: bool) -> list[FilePath]:
        """查询目录树所需的扁平节点列表。"""

        stmt = select(FilePath).where(FilePath.status == "active")
        if not include_hidden:
            stmt = stmt.where(FilePath.is_hidden.is_(False))
        stmt = stmt.order_by(FilePath.sort_index.asc(), FilePath.id.asc())
        return list(self.db.execute(stmt).scalars().all())

    def next_sort_index(self, parent_path_id: str | None) -> int:
        """返回父目录下一个排序号。"""

        stmt = select(func.max(FilePath.sort_index)).where(FilePath.parent_path_id == parent_path_id)
        max_index = self.db.execute(stmt).scalar_one_or_none()
        return int(max_index or 0) + 1

    def create(self, path: FilePath) -> FilePath:
        """创建目录节点，提交由 Service 统一处理。"""

        self.db.add(path)
        return path
