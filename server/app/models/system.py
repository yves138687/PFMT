from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.security import now_utc


class SystemSetting(Base):
    """系统配置表，保存加密、隐藏、AI、备份等全局开关。"""

    __tablename__ = "system_setting"
    __table_args__ = (
        CheckConstraint(
            "value_type IN ('string', 'boolean', 'number', 'json')",
            name="ck_system_setting_value_type",
        ),
        Index("idx_system_setting_group_name", "group_name"),
        Index("idx_system_setting_public_group", "is_public", "group_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    setting_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    setting_value: Mapped[str | None] = mapped_column(Text)
    value_type: Mapped[str] = mapped_column(String(32), nullable=False, default="string")
    group_name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=now_utc, onupdate=now_utc
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("user_account.user_id", onupdate="CASCADE", ondelete="SET NULL")
    )


class FileKeyVersion(Base):
    """文件加密 key；key_id 由系统生成，密钥材料保存在数据库中且不回显。"""

    __tablename__ = "file_key"
    __table_args__ = (
        CheckConstraint(
            "status IN ('expired', 'active_rotating', 'active_completed')",
            name="ck_file_key_status",
        ),
        Index("idx_file_key_active", "is_active", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    key_material: Mapped[str] = mapped_column(Text, nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active_completed")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime)
