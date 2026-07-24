from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.system import SystemSetting


class SettingRepository:
    """封装系统配置查询与 upsert。"""

    def __init__(self, db: Session):
        self.db = db

    def list_all(self) -> list[SystemSetting]:
        """查询全部系统配置。"""

        stmt = select(SystemSetting).order_by(SystemSetting.group_name.asc(), SystemSetting.setting_key.asc())
        return list(self.db.execute(stmt).scalars().all())

    def get_by_key(self, setting_key: str) -> SystemSetting | None:
        """按配置键查询配置项。"""

        stmt = select(SystemSetting).where(SystemSetting.setting_key == setting_key)
        return self.db.execute(stmt).scalar_one_or_none()

    def upsert(self, setting: SystemSetting) -> SystemSetting:
        """新增或更新配置项，由 Service 判断字段含义。"""

        existing = self.get_by_key(setting.setting_key)
        if existing is None:
            self.db.add(setting)
            return setting

        existing.setting_value = setting.setting_value
        existing.value_type = setting.value_type
        existing.group_name = setting.group_name
        existing.description = setting.description
        existing.is_public = setting.is_public
        existing.updated_by = setting.updated_by
        return existing
