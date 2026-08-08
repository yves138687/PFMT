from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_client_ip, get_current_user, get_db_session
from app.models.user import UserAccount
from app.schemas.path import PathCreateRequest, PathMoveRequest, PathRead, PathTreeNode, PathUpdateRequest
from app.services.path_service import PathService


router = APIRouter()


@router.get("/tree", response_model=list[PathTreeNode])
def get_path_tree(
    show_hidden: bool | None = Query(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[PathTreeNode]:
    """读取目录树，是否包含隐藏目录由当前会话开关决定。"""

    return PathService(db).get_tree(show_hidden=show_hidden, current_user=current_user)


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
        current_user=current_user,
        client_ip=client_ip,
    )


@router.patch("/{path_id}/move", response_model=PathRead)
def move_path(
    path_id: str,
    payload: PathMoveRequest,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    client_ip: str | None = Depends(get_client_ip),
) -> PathRead:
    """移动目录节点。"""

    return PathService(db).move_path(
        path_id=path_id,
        payload=payload,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.patch("/{path_id}", response_model=PathRead)
def update_path(
    path_id: str,
    payload: PathUpdateRequest,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    client_ip: str | None = Depends(get_client_ip),
) -> PathRead:
    """更新目录名称、描述和隐藏状态。"""

    return PathService(db).update_path(
        path_id=path_id,
        payload=payload,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.delete("/{path_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_path(
    path_id: str,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    client_ip: str | None = Depends(get_client_ip),
) -> None:
    """删除目录节点及其子内容。"""

    PathService(db).delete_path(
        path_id=path_id,
        current_user=current_user,
        client_ip=client_ip,
    )
