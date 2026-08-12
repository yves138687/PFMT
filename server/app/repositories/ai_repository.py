from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import AiMessage, AiTask


class AiTaskRepository:
    """封装 AI 任务与消息查询写入。"""

    def __init__(self, db: Session):
        self.db = db

    def create_task(self, task: AiTask) -> AiTask:
        self.db.add(task)
        return task

    def add_message(self, message: AiMessage) -> AiMessage:
        self.db.add(message)
        return message

    def get_by_task_id(self, task_id: str) -> AiTask | None:
        stmt = select(AiTask).where(AiTask.task_id == task_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_file_id(self, *, file_id: str, limit: int) -> list[AiTask]:
        stmt = (
            select(AiTask)
            .where(AiTask.file_id == file_id)
            .order_by(AiTask.created_at.desc(), AiTask.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def assistant_messages_by_task_ids(self, task_ids: Sequence[str]) -> dict[str, AiMessage]:
        if not task_ids:
            return {}
        stmt = (
            select(AiMessage)
            .where(AiMessage.task_id.in_(task_ids), AiMessage.role == "assistant")
            .order_by(AiMessage.created_at.desc(), AiMessage.id.desc())
        )
        messages: dict[str, AiMessage] = {}
        for message in self.db.execute(stmt).scalars().all():
            messages.setdefault(message.task_id, message)
        return messages
