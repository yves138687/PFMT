from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_client_ip, get_current_user, get_db_session
from app.models.user import UserAccount
from app.schemas.path import PathCreateRequest, PathRead, PathTreeNode
from app.services.path_service import PathService


router = APIRouter()


@router.get("/tree", response_model=list[PathTreeNode])
def get_path_tree(
    show_hidden: bool | None = Query(default=None),
    _current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[PathTreeNode]:
    """读取目录树，默认按系统配置过滤隐藏目录。"""

    return PathService(db).get_tree(show_hidden=show_hidden)


@router.post("", response_model=PathRead, status_code=status.HTTP_201_CREATED)
def create_path(
    payload: PathCreateRequest,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    client_ip: str | None = Depends(get_client_ip),
) -> PathRead:
    """创建目录节点。"""

    return PathService(db).create_path(
        payload=payload,
        user_id=current_user.user_id,
        client_ip=client_ip,
    )
