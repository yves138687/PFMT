import logging

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_session_factory
from app.core.security import hash_password
from app.models.file import FilePath
from app.models.system import SystemSetting
from app.models.user import UserAccount
from app.repositories.path_repository import PathRepository
from app.repositories.setting_repository import SettingRepository
from app.repositories.user_repository import UserRepository
from app.services.setting_service import DEFAULT_SETTINGS


def seed_application_data(settings: Settings) -> None:
    """启动时 seed 管理员账号、根目录和默认系统配置。"""

    db = get_session_factory(settings)()
    try:
        _seed_admin(db, settings)
        _seed_root_path(db)
        _seed_default_settings(db, settings)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _seed_admin(db: Session, settings: Settings) -> None:
    """不存在管理员时创建默认单用户账号。"""

    repository = UserRepository(db)
    if repository.get_by_username(settings.admin_username) is not None:
        return

    repository.create(
        UserAccount(
            user_id="user_admin",
            username=settings.admin_username,
            password_hash=hash_password(settings.admin_password),
            display_name=settings.admin_display_name,
            status="active",
        )
    )
    if settings.admin_password == "admin123456":
        logging.getLogger("pfmt.security").warning(
            "当前使用开发默认管理员密码，请在生产环境通过 PFMT_ADMIN_PASSWORD 修改"
        )


def _seed_root_path(db: Session) -> None:
    """不存在根目录时创建 root 节点。"""

    repository = PathRepository(db)
    if repository.get_by_path_id("root") is not None:
        return

    repository.create(
        FilePath(
            path_id="root",
            parent_path_id=None,
            path_name="根目录",
            path_type="normal",
            path_level=0,
            sort_index=0,
            full_path="/",
            description="系统根目录",
            is_hidden=False,
            status="active",
        )
    )


def _seed_default_settings(db: Session, settings: Settings) -> None:
    """写入缺省配置；已有配置不覆盖，避免重启改掉用户设置。"""

    repository = SettingRepository(db)
    for item in DEFAULT_SETTINGS:
        if repository.get_by_key(item["setting_key"]) is not None:
            continue
        value = item["setting_value"]
        if item["setting_key"] == "storage.local_root":
            value = settings.storage_root_path.as_posix()
        elif item["setting_key"] == "storage.encryption_enabled":
            value = "true" if settings.file_encryption_enabled else "false"
        elif item["setting_key"] == "hidden.feature_enabled":
            value = "true" if settings.hidden_feature_enabled else "false"
        elif item["setting_key"] == "hidden.show_hidden_default":
            value = "true" if settings.show_hidden_by_default else "false"
        elif item["setting_key"] == "ai.feature_enabled":
            value = "true" if settings.ai_enabled else "false"
        elif item["setting_key"] == "backup.git_enabled":
            value = "true" if settings.backup_enabled else "false"
        repository.upsert(
            SystemSetting(
                setting_key=item["setting_key"],
                setting_value=value,
                value_type=item["value_type"],
                group_name=item["group_name"],
                description=item["description"],
                is_public=item["is_public"],
            )
        )
