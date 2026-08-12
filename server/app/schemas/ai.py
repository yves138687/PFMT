from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


AiTaskType = Literal["summary", "qa", "polish", "translate", "continue"]
AiTaskStatus = Literal["pending", "running", "success", "failed", "cancelled"]


class AiTaskCreateRequest(BaseModel):
    """创建一次文档页 AI 调用。"""

    file_id: str = Field(max_length=64)
    task_type: AiTaskType
    prompt: str | None = Field(default=None, max_length=4000)
    selected_text: str | None = Field(default=None, max_length=12000)
    provider_id: str | None = Field(default=None, max_length=128)


class AiTaskResponse(BaseModel):
    task_id: str
    task_type: str
    task_status: AiTaskStatus
    answer: str | None = None
    read_scope: str
    model_provider: str | None = None
    model_name: str | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class AiTaskListResponse(BaseModel):
    items: list[AiTaskResponse]
    total: int
