from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.security import now_utc


class AiTask(Base):
    """AI 调用任务表，记录用户显式授权范围内的一次模型调用。"""

    __tablename__ = "ai_task"
    __table_args__ = (
        CheckConstraint(
            "task_type IN ('summary', 'qa', 'rewrite', 'translate', 'continue', 'polish', 'replace')",
            name="ck_ai_task_type",
        ),
        CheckConstraint(
            "task_status IN ('pending', 'running', 'success', 'failed', 'cancelled')",
            name="ck_ai_task_status",
        ),
        Index("idx_ai_task_file_id", "file_id"),
        Index("idx_ai_task_status_created_at", "task_status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("file_info.file_id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False
    )
    selected_range: Mapped[str | None] = mapped_column(Text)
    read_scope: Mapped[str] = mapped_column(Text, nullable=False)
    model_provider: Mapped[str | None] = mapped_column(String(128))
    model_name: Mapped[str | None] = mapped_column(String(128))
    prompt_text: Mapped[str | None] = mapped_column(Text)
    task_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("user_account.user_id", onupdate="CASCADE", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class AiMessage(Base):
    """AI 任务关联消息，保存请求与模型回答。"""

    __tablename__ = "ai_message"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_ai_message_role"),
        Index("idx_ai_message_task_id_created_at", "task_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("ai_task.task_id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    message_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc)
