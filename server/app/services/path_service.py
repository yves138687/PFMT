from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.file import FilePath
from app.repositories.path_repository import PathRepository
from app.schemas.path import PathCreateRequest, PathRead, PathTreeNode
from app.services.audit_service import AuditService
from app.services.setting_service import SettingService
from app.utils.ids import new_business_id


class PathService:
    """目录服务，负责目录树构建、隐藏过滤和创建目录业务。"""

    def __init__(self, db: Session):
        self.db = db
        self.repository = PathRepository(db)
        self.setting_service = SettingService(db)
        self.audit_service = AuditService(db)

    def get_tree(self, *, show_hidden: bool | None = None) -> list[PathTreeNode]:
        """读取目录树；未显式传 show_hidden 时按系统配置决定隐藏过滤。"""

        include_hidden = self._include_hidden(show_hidden)
        paths = self.repository.list_active(include_hidden=include_hidden)
        node_map = {path.path_id: self._to_tree_node(path) for path in paths}
        roots: list[PathTreeNode] = []

        for path in paths:
            node = node_map[path.path_id]
            if path.parent_path_id and path.parent_path_id in node_map:
                node_map[path.parent_path_id].children.append(node)
            elif path.parent_path_id is None:
                roots.append(node)

        return roots

    def create_path(
        self,
        *,
        payload: PathCreateRequest,
        user_id: str,
        client_ip: str | None,
    ) -> PathRead:
        """创建目录并写入审计日志。"""

        parent = self.repository.get_active_by_path_id(payload.parent_path_id)
        if parent is None:
            self.audit_service.record(
                user_id=user_id,
                action_type="create_path",
                target_type="file_path",
                result="failed",
                detail={"reason": "parent_not_found"},
                client_ip=client_ip,
            )
            self.db.commit()
            raise NotFoundError("父目录不存在")

        full_path = self._join_full_path(parent.full_path, payload.path_name)
        if self.repository.get_by_full_path(full_path) is not None:
            self.audit_service.record(
                user_id=user_id,
                action_type="create_path",
                target_type="file_path",
                result="failed",
                detail={"reason": "duplicate_full_path"},
                client_ip=client_ip,
            )
            self.db.commit()
            raise ConflictError("同名目录已存在")

        path = FilePath(
            path_id=new_business_id("path"),
            parent_path_id=parent.path_id,
            path_name=payload.path_name,
            path_type=payload.path_type,
            path_level=parent.path_level + 1,
            sort_index=self.repository.next_sort_index(parent.path_id),
            full_path=full_path,
            description=payload.description,
            is_hidden=payload.is_hidden,
        )
        self.repository.create(path)
        self.audit_service.record(
            user_id=user_id,
            action_type="create_path",
            target_type="file_path",
            target_id=path.path_id,
            result="success",
            detail={"path_type": path.path_type, "is_hidden": path.is_hidden},
            client_ip=client_ip,
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("目录创建冲突") from exc
        self.db.refresh(path)
        return self._to_read(path)

    def _include_hidden(self, show_hidden: bool | None) -> bool:
        """依据隐藏开关和请求参数决定是否返回隐藏目录。"""

        feature_enabled = self.setting_service.get_bool("hidden.feature_enabled", True)
        if not feature_enabled:
            return True
        if show_hidden is not None:
            return show_hidden
        return self.setting_service.get_bool("hidden.show_hidden_default", False)

    @staticmethod
    def _join_full_path(parent_full_path: str, path_name: str) -> str:
        """拼出数据库冗余的完整路径。"""

        if parent_full_path == "/":
            return f"/{path_name}"
        return f"{parent_full_path.rstrip('/')}/{path_name}"

    def _to_tree_node(self, path: FilePath) -> PathTreeNode:
        """将目录模型转换为树节点响应。"""

        return PathTreeNode(**self._to_read(path).model_dump(), children=[])

    @staticmethod
    def _to_read(path: FilePath) -> PathRead:
        """将目录 ORM 模型转换为基础响应。"""

        return PathRead(
            path_id=path.path_id,
            parent_path_id=path.parent_path_id,
            path_name=path.path_name,
            path_type=path.path_type,  # type: ignore[arg-type]
            path_level=path.path_level,
            sort_index=path.sort_index,
            full_path=path.full_path,
            description=path.description,
            is_hidden=path.is_hidden,
            status=path.status,
            created_at=path.created_at,
            updated_at=path.updated_at,
        )
