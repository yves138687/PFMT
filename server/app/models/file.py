from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.security import now_utc


class FilePath(Base):
    """目录树节点；path_type 仅作为历史兼容字段保留，隐藏规则以 is_hidden 为准。"""

    __tablename__ = "file_path"
    __table_args__ = (
        CheckConstraint("path_type IN ('normal', 'private')", name="ck_file_path_path_type"),
        CheckConstraint("path_level >= 0", name="ck_file_path_level"),
        CheckConstraint("status IN ('active', 'deleted')", name="ck_file_path_status"),
        UniqueConstraint("full_path", name="uq_file_path_full_path"),
        Index("idx_file_path_parent_path_id", "parent_path_id"),
        Index("idx_file_path_hidden_status", "is_hidden", "status"),
        Index("idx_file_path_type_status", "path_type", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    parent_path_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("file_path.path_id", onupdate="CASCADE", ondelete="SET NULL")
    )
    path_name: Mapped[str] = mapped_column(String(255), nullable=False)
    path_type: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    path_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    full_path: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=now_utc, onupdate=now_utc
    )


class FileInfo(Base):
    """文件元数据主表，文件对象映射、摘要和加密信息都集中在这里。"""

    __tablename__ = "file_info"
    __table_args__ = (
        CheckConstraint(
            "file_type IN ('text', 'image', 'video', 'pdf', 'audio', 'other')",
            name="ck_file_info_file_type",
        ),
        CheckConstraint("size_bytes >= 0", name="ck_file_info_size_bytes"),
        CheckConstraint("summary_source IN ('manual', 'ai')", name="ck_file_info_summary_source"),
        CheckConstraint(
            "visibility_type IN ('normal', 'private')", name="ck_file_info_visibility_type"
        ),
        CheckConstraint(
            "status IN ('active', 'deleted', 'archived')", name="ck_file_info_status"
        ),
        UniqueConstraint("storage_object_name", name="uq_file_info_storage_object_name"),
        UniqueConstraint("storage_path", name="uq_file_info_storage_path"),
        Index("idx_file_info_path_id", "path_id"),
        Index("idx_file_info_type_status", "file_type", "status"),
        Index("idx_file_info_hidden_status", "is_hidden", "status"),
        Index("idx_file_info_visibility_status", "visibility_type", "status"),
        Index("idx_file_info_created_at", "created_at"),
        Index("idx_file_info_updated_at", "updated_at"),
        Index("idx_file_info_last_accessed_at", "last_accessed_at"),
        Index("idx_file_info_checksum_sha256", "checksum_sha256"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    path_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("file_path.path_id", onupdate="CASCADE", ondelete="RESTRICT")
    )
    original_name: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_object_name: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(64), nullable=False, default="local")
    mime_type: Mapped[str | None] = mapped_column(String(255))
    file_ext: Mapped[str | None] = mapped_column(String(32))
    file_type: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checksum_sha256: Mapped[str | None] = mapped_column(String(128))
    encryption_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    key_wrap_version: Mapped[str | None] = mapped_column(String(64))
    remark: Mapped[str | None] = mapped_column(Text)
    summary_content: Mapped[str | None] = mapped_column(Text)
    summary_source: Mapped[str | None] = mapped_column(String(32))
    summary_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    visibility_type: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("user_account.user_id", onupdate="CASCADE", ondelete="SET NULL")
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("user_account.user_id", onupdate="CASCADE", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=now_utc, onupdate=now_utc
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime)


class FileTag(Base):
    """文件标签定义，仅用于元数据组织和搜索。"""

    __tablename__ = "file_tag"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'deleted')", name="ck_file_tag_status"),
        UniqueConstraint("tag_id", name="uq_file_tag_tag_id"),
        UniqueConstraint("tag_name", name="uq_file_tag_tag_name"),
        Index("idx_file_tag_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tag_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tag_name: Mapped[str] = mapped_column(String(128), nullable=False)
    tag_color: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=now_utc, onupdate=now_utc
    )


class FileTagRel(Base):
    """文件与标签的多对多关系。"""

    __tablename__ = "file_tag_rel"
    __table_args__ = (
        UniqueConstraint("file_id", "tag_id", name="uq_file_tag_rel_file_tag"),
        Index("idx_file_tag_rel_file_id", "file_id"),
        Index("idx_file_tag_rel_tag_id", "tag_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("file_info.file_id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False
    )
    tag_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("file_tag.tag_id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc)
