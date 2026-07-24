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
