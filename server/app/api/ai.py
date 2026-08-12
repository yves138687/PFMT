from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_client_ip, get_current_user, get_db_session
from app.core.config import Settings, get_settings
from app.models.user import UserAccount
from app.schemas.ai import AiTaskCreateRequest, AiTaskListResponse, AiTaskResponse
from app.schemas.file import FileDetailResponse
from app.services.ai_service import AiService


router = APIRouter()


@router.post("/tasks", response_model=AiTaskResponse)
def create_ai_task(
    payload: AiTaskCreateRequest,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> AiTaskResponse:
    """同步执行一次文档页 AI 任务。"""

    return AiService(db, settings).create_task(
        payload=payload,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.get("/tasks", response_model=AiTaskListResponse)
def list_ai_tasks(
    file_id: str = Query(max_length=64),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> AiTaskListResponse:
    """读取当前文件最近 AI 调用记录。"""

    return AiService(db, settings).list_tasks(
        file_id=file_id,
        limit=limit,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.post("/tasks/{task_id}/write-summary", response_model=FileDetailResponse)
def write_ai_summary(
    task_id: str,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> FileDetailResponse:
    """把用户确认的 AI 总结写入文件摘要。"""

    return AiService(db, settings).write_summary(
        task_id=task_id,
        current_user=current_user,
        client_ip=client_ip,
    )
