from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import now_utc
from app.models.file import FileInfo, FileTag, FileTagRel


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

    def get_active_by_name(
        self,
        *,
        path_id: str,
        original_name: str,
        exclude_file_id: str | None = None,
    ) -> FileInfo | None:
        """按目录和展示文件名查询未删除文件，用于保持展示树一一对应。"""

        stmt = select(FileInfo).where(
            FileInfo.path_id == path_id,
            FileInfo.original_name == original_name,
            FileInfo.status == "active",
        )
        if exclude_file_id is not None:
            stmt = stmt.where(FileInfo.file_id != exclude_file_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_active_by_file_ids(self, file_ids: Sequence[str]) -> list[FileInfo]:
        """按文件 ID 批量查询未删除文件。"""

        if not file_ids:
            return []
        stmt = select(FileInfo).where(FileInfo.file_id.in_(file_ids), FileInfo.status == "active")
        return list(self.db.execute(stmt).scalars().all())

    def search_active(self, *, query: str, include_hidden: bool, limit: int) -> list[FileInfo]:
        """按文件元数据和标签搜索，不读取文件本体。"""

        keyword = f"%{query.lower()}%"
        stmt = (
            select(FileInfo)
            .outerjoin(FileTagRel, FileInfo.file_id == FileTagRel.file_id)
            .outerjoin(FileTag, FileTagRel.tag_id == FileTag.tag_id)
            .where(FileInfo.status == "active")
            .where(
                or_(
                    FileInfo.original_name.ilike(keyword),
                    FileInfo.file_type.ilike(keyword),
                    FileInfo.file_ext.ilike(keyword),
                    FileInfo.mime_type.ilike(keyword),
                    FileInfo.remark.ilike(keyword),
                    FileInfo.summary_content.ilike(keyword),
                    FileTag.tag_name.ilike(keyword),
                )
            )
            .distinct()
            .order_by(FileInfo.updated_at.desc(), FileInfo.id.desc())
            .limit(limit)
        )
        if not include_hidden:
            stmt = stmt.where(FileInfo.is_hidden.is_(False))
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

    def update_metadata(
        self,
        file_info: FileInfo,
        *,
        original_name: str | None,
        remark: str | None,
        summary_content: str | None,
        is_hidden: bool | None,
        user_id: str,
    ) -> None:
        """更新文件业务元数据。"""

        if original_name is not None:
            file_info.original_name = original_name
        file_info.remark = remark
        file_info.summary_content = summary_content
        file_info.summary_source = "manual" if summary_content else None
        file_info.summary_updated_at = now_utc() if summary_content else None
        if is_hidden is not None:
            file_info.is_hidden = is_hidden
        file_info.updated_by = user_id
        file_info.updated_at = now_utc()

    def update_content_metadata(
        self,
        file_info: FileInfo,
        *,
        size_bytes: int,
        checksum_sha256: str,
        key_wrap_version: str | None,
        user_id: str,
    ) -> None:
        """更新文件本体变化后的元数据。"""

        file_info.size_bytes = size_bytes
        file_info.checksum_sha256 = checksum_sha256
        file_info.key_wrap_version = key_wrap_version
        file_info.updated_by = user_id
        file_info.updated_at = now_utc()

    def update_upload_content_metadata(
        self,
        file_info: FileInfo,
        *,
        mime_type: str | None,
        file_ext: str | None,
        file_type: str,
        size_bytes: int,
        checksum_sha256: str,
        encryption_enabled: bool,
        key_wrap_version: str | None,
        is_hidden: bool,
        user_id: str,
    ) -> None:
        """更新覆盖上传后的文件内容元数据。"""

        file_info.mime_type = mime_type
        file_info.file_ext = file_ext
        file_info.file_type = file_type
        file_info.size_bytes = size_bytes
        file_info.checksum_sha256 = checksum_sha256
        file_info.encryption_enabled = encryption_enabled
        file_info.key_wrap_version = key_wrap_version
        file_info.is_hidden = is_hidden
        file_info.updated_by = user_id
        file_info.updated_at = now_utc()

    def update_storage_path(self, file_info: FileInfo, *, storage_path: str, user_id: str) -> None:
        """更新文件移动后的真实存储路径。"""

        file_info.storage_path = storage_path
        file_info.updated_by = user_id
        file_info.updated_at = now_utc()

    def move_to_path(
        self,
        file_info: FileInfo,
        *,
        path_id: str,
        original_name: str | None = None,
        visibility_type: str,
        user_id: str,
    ) -> None:
        """移动文件到新的业务目录。"""

        file_info.path_id = path_id
        if original_name is not None:
            file_info.original_name = original_name
        file_info.visibility_type = visibility_type
        file_info.updated_by = user_id
        file_info.updated_at = now_utc()

    def soft_delete(self, file_info: FileInfo, *, user_id: str) -> None:
        """软删除文件元数据。"""

        file_info.status = "deleted"
        file_info.updated_by = user_id
        file_info.updated_at = now_utc()


class FileTagRepository:
    """封装文件标签查询与绑定。"""

    def __init__(self, db: Session):
        self.db = db

    def list_active(self) -> list[FileTag]:
        stmt = select(FileTag).where(FileTag.status == "active").order_by(FileTag.tag_name.asc())
        return list(self.db.execute(stmt).scalars().all())

    def get_active_by_name(self, tag_name: str) -> FileTag | None:
        stmt = select(FileTag).where(FileTag.tag_name == tag_name, FileTag.status == "active")
        return self.db.execute(stmt).scalar_one_or_none()

    def get_active_by_file_id(self, file_id: str) -> list[FileTag]:
        stmt = (
            select(FileTag)
            .join(FileTagRel, FileTag.tag_id == FileTagRel.tag_id)
            .where(FileTagRel.file_id == file_id, FileTag.status == "active")
            .order_by(FileTag.tag_name.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_active_by_file_ids(self, file_ids: Sequence[str]) -> dict[str, list[FileTag]]:
        if not file_ids:
            return {}
        stmt = (
            select(FileTagRel.file_id, FileTag)
            .join(FileTag, FileTagRel.tag_id == FileTag.tag_id)
            .where(FileTagRel.file_id.in_(file_ids), FileTag.status == "active")
            .order_by(FileTag.tag_name.asc())
        )
        grouped: dict[str, list[FileTag]] = {}
        for file_id, tag in self.db.execute(stmt).all():
            grouped.setdefault(file_id, []).append(tag)
        return grouped

    def create(self, tag: FileTag) -> FileTag:
        self.db.add(tag)
        return tag

    def replace_file_tags(self, *, file_id: str, tags: Sequence[FileTag]) -> None:
        existing = self.db.execute(select(FileTagRel).where(FileTagRel.file_id == file_id)).scalars().all()
        for rel in existing:
            self.db.delete(rel)
        for tag in tags:
            self.db.add(FileTagRel(file_id=file_id, tag_id=tag.tag_id))
