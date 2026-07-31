from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import now_utc
from app.models.file import FilePath
from app.models.user import UserAccount
from app.repositories.file_repository import FileRepository
from app.repositories.path_repository import PathRepository
from app.schemas.path import PathCreateRequest, PathMoveRequest, PathRead, PathTreeNode, PathUpdateRequest
from app.services.audit_service import AuditService
from app.services.setting_service import SettingService
from app.services.storage_service import StorageService
from app.utils.ids import new_business_id


class PathService:
    """目录服务，负责目录树构建、隐藏过滤和创建目录业务。"""

    def __init__(self, db: Session, settings: Settings | None = None):
        """初始化目录服务依赖的仓储、配置和审计服务。"""

        self.db = db
        self.settings = settings or get_settings()
        self.repository = PathRepository(db)
        self.file_repository = FileRepository(db)
        self.setting_service = SettingService(db)
        self.audit_service = AuditService(db)
        self.storage_service = StorageService(self.settings)

    def get_tree(self, *, show_hidden: bool | None = None, current_user: UserAccount | None = None) -> list[PathTreeNode]:
        """读取目录树；是否包含隐藏目录只由当前会话开关决定。"""

        include_hidden = self._include_hidden(current_user=current_user)
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
            path_type="normal",
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
            detail={"is_hidden": path.is_hidden},
            client_ip=client_ip,
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("目录创建冲突") from exc
        self.db.refresh(path)
        return self._to_read(path)

    def move_path(
        self,
        *,
        path_id: str,
        payload: PathMoveRequest,
        user_id: str,
        client_ip: str | None,
    ) -> PathRead:
        """移动目录到新的父目录，并同步更新子目录冗余 full_path。"""

        action_type = "move_path"
        path = self.repository.get_active_by_path_id(path_id)
        if path is None:
            self._record_path_action_failure(
                user_id=user_id,
                path_id=path_id,
                action_type=action_type,
                reason="path_not_found",
                client_ip=client_ip,
            )
            raise NotFoundError("目录不存在")

        if path.path_id == "root":
            self._record_path_action_failure(
                user_id=user_id,
                path_id=path_id,
                action_type=action_type,
                reason="root_not_movable",
                client_ip=client_ip,
            )
            raise ConflictError("根目录不能移动")

        parent = self.repository.get_active_by_path_id(payload.parent_path_id)
        if parent is None:
            self._record_path_action_failure(
                user_id=user_id,
                path_id=path_id,
                action_type=action_type,
                reason="parent_not_found",
                client_ip=client_ip,
            )
            raise NotFoundError("目标目录不存在")

        subtree = self._active_subtree(path.path_id)
        subtree_ids = {item.path_id for item in subtree}
        if parent.path_id in subtree_ids:
            self._record_path_action_failure(
                user_id=user_id,
                path_id=path_id,
                action_type=action_type,
                reason="parent_inside_subtree",
                client_ip=client_ip,
            )
            raise ConflictError("不能移动到自身或子目录")

        old_full_path = path.full_path
        new_full_path = self._join_full_path(parent.full_path, path.path_name)
        new_full_paths = {
            item.path_id: new_full_path
            if item.path_id == path.path_id
            else f"{new_full_path}{item.full_path.removeprefix(old_full_path)}"
            for item in subtree
        }
        active_paths = [
            item for item in self.repository.list_active(include_hidden=True) if item.path_id not in subtree_ids
        ]
        existing_full_paths = {item.full_path for item in active_paths}
        if any(full_path in existing_full_paths for full_path in new_full_paths.values()):
            self._record_path_action_failure(
                user_id=user_id,
                path_id=path_id,
                action_type=action_type,
                reason="duplicate_full_path",
                client_ip=client_ip,
            )
            raise ConflictError("目标目录下已存在同名目录")

        updated_at = now_utc()
        level_delta = parent.path_level + 1 - path.path_level
        path.parent_path_id = parent.path_id
        path.sort_index = self.repository.next_sort_index(parent.path_id)
        for item in subtree:
            item.full_path = new_full_paths[item.path_id]
            item.path_level += level_delta
            item.updated_at = updated_at

        self.audit_service.record(
            user_id=user_id,
            action_type=action_type,
            target_type="file_path",
            target_id=path.path_id,
            result="success",
            detail={"parent_path_id": parent.path_id, "affected_paths": len(subtree)},
            client_ip=client_ip,
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("目录移动冲突") from exc
        self.db.refresh(path)
        return self._to_read(path)

    def update_path(
        self,
        *,
        path_id: str,
        payload: PathUpdateRequest,
        user_id: str,
        client_ip: str | None,
    ) -> PathRead:
        """更新目录名称、描述和隐藏状态，并同步子目录 full_path。"""

        action_type = "update_path"
        path = self.repository.get_active_by_path_id(path_id)
        if path is None:
            self._record_path_action_failure(
                user_id=user_id,
                path_id=path_id,
                action_type=action_type,
                reason="path_not_found",
                client_ip=client_ip,
            )
            raise NotFoundError("目录不存在")
        if path.path_id == "root" and payload.path_name is not None:
            self._record_path_action_failure(
                user_id=user_id,
                path_id=path_id,
                action_type=action_type,
                reason="root_not_renamable",
                client_ip=client_ip,
            )
            raise ConflictError("根目录不能重命名")

        old_full_path = path.full_path
        if payload.path_name is not None and payload.path_name != path.path_name:
            parent_full_path = "/"
            if path.parent_path_id is not None:
                parent = self.repository.get_active_by_path_id(path.parent_path_id)
                if parent is None:
                    raise NotFoundError("父目录不存在")
                parent_full_path = parent.full_path
            new_full_path = self._join_full_path(parent_full_path, payload.path_name)
            existing = self.repository.get_by_full_path(new_full_path)
            if existing is not None and existing.path_id != path.path_id and existing.status == "active":
                self._record_path_action_failure(
                    user_id=user_id,
                    path_id=path_id,
                    action_type=action_type,
                    reason="duplicate_full_path",
                    client_ip=client_ip,
                )
                raise ConflictError("同名目录已存在")
            path.path_name = payload.path_name
            subtree = self._active_subtree(path.path_id)
            for item in subtree:
                item.full_path = new_full_path if item.path_id == path.path_id else f"{new_full_path}{item.full_path.removeprefix(old_full_path)}"
                item.updated_at = now_utc()

        if payload.description is not None:
            path.description = payload.description if payload.description.strip() else None
        if payload.is_hidden is not None:
            path.is_hidden = payload.is_hidden
        path.updated_at = now_utc()
        self.audit_service.record(
            user_id=user_id,
            action_type=action_type,
            target_type="file_path",
            target_id=path.path_id,
            result="success",
            detail={"renamed": payload.path_name is not None, "is_hidden": path.is_hidden},
            client_ip=client_ip,
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("目录更新冲突") from exc
        self.db.refresh(path)
        return self._to_read(path)

    def delete_path(
        self,
        *,
        path_id: str,
        user_id: str,
        client_ip: str | None,
    ) -> None:
        """软删除目录、子目录和其中的文件，并清理文件对象。"""

        action_type = "delete_path"
        path = self.repository.get_active_by_path_id(path_id)
        if path is None:
            self._record_path_action_failure(
                user_id=user_id,
                path_id=path_id,
                action_type=action_type,
                reason="path_not_found",
                client_ip=client_ip,
            )
            raise NotFoundError("目录不存在")

        if path.path_id == "root":
            self._record_path_action_failure(
                user_id=user_id,
                path_id=path_id,
                action_type=action_type,
                reason="root_not_deletable",
                client_ip=client_ip,
            )
            raise ConflictError("根目录不能删除")

        subtree = self._active_subtree(path.path_id)
        path_ids = [item.path_id for item in subtree]
        files = self.file_repository.list_active_by_path_ids(path_ids)
        updated_at = now_utc()

        for file_info in files:
            self.file_repository.soft_delete(file_info, user_id=user_id)

        for item in subtree:
            item.status = "deleted"
            item.full_path = self._deleted_full_path(item)
            item.updated_at = updated_at

        self.audit_service.record(
            user_id=user_id,
            action_type=action_type,
            target_type="file_path",
            target_id=path.path_id,
            result="success",
            detail={"affected_paths": len(subtree), "affected_files": len(files)},
            client_ip=client_ip,
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("目录删除冲突") from exc

        for file_info in files:
            self.storage_service.delete_object(file_info.storage_path)

    def _include_hidden(self, *, current_user: UserAccount | None) -> bool:
        """依据隐藏功能开关和当前会话状态决定是否返回隐藏目录。"""

        feature_enabled = self.setting_service.get_bool("hidden.feature_enabled", True)
        session_enabled = bool(getattr(current_user, "_pfmt_show_hidden_enabled", False))
        return feature_enabled and session_enabled

    @staticmethod
    def _join_full_path(parent_full_path: str, path_name: str) -> str:
        """拼出数据库冗余的完整路径。"""

        if parent_full_path == "/":
            return f"/{path_name}"
        return f"{parent_full_path.rstrip('/')}/{path_name}"

    def _active_subtree(self, path_id: str) -> list[FilePath]:
        """按父子关系取出一个目录的未删除子树。"""

        paths = self.repository.list_active(include_hidden=True)
        children_by_parent: dict[str | None, list[FilePath]] = {}
        root: FilePath | None = None
        for path in paths:
            children_by_parent.setdefault(path.parent_path_id, []).append(path)
            if path.path_id == path_id:
                root = path

        if root is None:
            return []

        subtree: list[FilePath] = []
        stack = [root]
        while stack:
            current = stack.pop()
            subtree.append(current)
            stack.extend(children_by_parent.get(current.path_id, []))
        return subtree

    @staticmethod
    def _deleted_full_path(path: FilePath) -> str:
        """给软删除目录改写唯一路径，释放原 full_path 供重新创建。"""

        return f"/__deleted__/{path.path_id}"

    def _record_path_action_failure(
        self,
        *,
        user_id: str,
        path_id: str,
        action_type: str,
        reason: str,
        client_ip: str | None,
    ) -> None:
        """目录操作失败时写入审计。"""

        self.audit_service.record(
            user_id=user_id,
            action_type=action_type,
            target_type="file_path",
            target_id=path_id,
            result="failed",
            detail={"reason": reason},
            client_ip=client_ip,
        )
        self.db.commit()

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
            path_level=path.path_level,
            sort_index=path.sort_index,
            full_path=path.full_path,
            description=path.description,
            is_hidden=path.is_hidden,
            status=path.status,
            created_at=path.created_at,
            updated_at=path.updated_at,
        )
