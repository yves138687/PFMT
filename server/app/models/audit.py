from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.security import now_utc


class AuditLog(Base):
    """审计日志表，记录登录、配置、目录、文件访问等关键操作。"""

    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint("action_result IN ('success', 'failed')", name="ck_audit_log_result"),
        Index("idx_audit_log_user_id_created_at", "user_id", "created_at"),
        Index("idx_audit_log_target", "target_type", "target_id"),
        Index("idx_audit_log_action_type_created_at", "action_type", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    log_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("user_account.user_id", onupdate="CASCADE", ondelete="SET NULL")
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[str | None] = mapped_column(String(64))
    action_result: Mapped[str] = mapped_column(String(32), nullable=False, default="success")
    detail: Mapped[str | None] = mapped_column(Text)
    client_ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc)
