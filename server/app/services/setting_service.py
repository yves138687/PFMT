import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.system import SystemSetting
from app.repositories.setting_repository import SettingRepository
from app.schemas.setting import SettingItem, SettingUpdateRequest
from app.services.audit_service import AuditService


class SettingService:
    """系统配置服务，统一处理配置值类型转换和写审计。"""

    def __init__(self, db: Session):
        self.db = db
        self.repository = SettingRepository(db)
        self.audit_service = AuditService(db)

    @staticmethod
    def parse_value(raw_value: str | None, value_type: str) -> Any:
        """将数据库字符串值转换为接口返回的业务值。"""

        if raw_value is None:
            return None
        if value_type == "boolean":
            return raw_value.lower() in {"1", "true", "yes", "on"}
        if value_type == "number":
            try:
                return int(raw_value)
            except ValueError:
                return float(raw_value)
        if value_type == "json":
            return json.loads(raw_value)
        return raw_value

    @staticmethod
    def serialize_value(value: Any, value_type: str) -> str | None:
        """将接口传入的业务值转换为数据库字符串。"""

        if value is None:
            return None
        if value_type == "boolean":
            if isinstance(value, str):
                return "true" if value.strip().lower() in {"1", "true", "yes", "on"} else "false"
            return "true" if bool(value) else "false"
        if value_type == "json":
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return str(value)

    @staticmethod
    def infer_value_type(value: Any) -> str:
        """新配置未显式指定类型时，根据 Python 值推断 value_type。"""

        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int | float):
            return "number"
        if isinstance(value, dict | list):
            return "json"
        return "string"

    def list_settings(self) -> list[SettingItem]:
        """读取全部系统配置。"""

        return [self._to_schema(item) for item in self.repository.list_all()]

    def get_bool(self, setting_key: str, default: bool = False) -> bool:
        """读取布尔配置，缺失或解析失败时返回默认值。"""

        setting = self.repository.get_by_key(setting_key)
        if setting is None:
            return default
        return bool(self.parse_value(setting.setting_value, setting.value_type))

    def update_setting(
        self,
        *,
        setting_key: str,
        payload: SettingUpdateRequest,
        updated_by: str,
        client_ip: str | None,
    ) -> SettingItem:
        """更新或创建配置项，并记录审计日志。"""

        existing = self.repository.get_by_key(setting_key)
        value_type = payload.value_type or (existing.value_type if existing else self.infer_value_type(payload.setting_value))
        setting = SystemSetting(
            setting_key=setting_key,
            setting_value=self.serialize_value(payload.setting_value, value_type),
            value_type=value_type,
            group_name=payload.group_name or (existing.group_name if existing else "custom"),
            description=payload.description if payload.description is not None else (existing.description if existing else None),
            is_public=payload.is_public if payload.is_public is not None else (existing.is_public if existing else False),
            updated_by=updated_by,
        )

        saved = self.repository.upsert(setting)
        self.audit_service.record(
            user_id=updated_by,
            action_type="update_setting",
            target_type="system_setting",
            target_id=setting_key,
            result="success",
            detail={"value_type": value_type, "group_name": saved.group_name},
            client_ip=client_ip,
        )
        self.db.commit()
        self.db.refresh(saved)
        return self._to_schema(saved)

    def _to_schema(self, setting: SystemSetting) -> SettingItem:
        """将 ORM 配置模型转换为响应模型。"""

        return SettingItem(
            setting_key=setting.setting_key,
            setting_value=self.parse_value(setting.setting_value, setting.value_type),
            value_type=setting.value_type,  # type: ignore[arg-type]
            group_name=setting.group_name,
            description=setting.description,
            is_public=setting.is_public,
            updated_at=setting.updated_at,
            updated_by=setting.updated_by,
        )


DEFAULT_SETTINGS = [
    {
        "setting_key": "storage.encryption_enabled",
        "setting_value": "true",
        "value_type": "boolean",
        "group_name": "storage",
        "description": "是否默认启用文件本体加密",
        "is_public": True,
    },
    {
        "setting_key": "storage.local_root",
        "setting_value": None,
        "value_type": "string",
        "group_name": "storage",
        "description": "本地存储根路径",
        "is_public": True,
    },
    {
        "setting_key": "hidden.feature_enabled",
        "setting_value": "true",
        "value_type": "boolean",
        "group_name": "hidden",
        "description": "是否启用文件隐藏功能",
        "is_public": True,
    },
    {
        "setting_key": "hidden.show_hidden_default",
        "setting_value": "false",
        "value_type": "boolean",
        "group_name": "hidden",
        "description": "默认是否展示隐藏内容",
        "is_public": False,
    },
    {
        "setting_key": "ai.feature_enabled",
        "setting_value": "false",
        "value_type": "boolean",
        "group_name": "ai",
        "description": "是否启用文件内 AI 能力",
        "is_public": True,
    },
    {
        "setting_key": "backup.git_enabled",
        "setting_value": "false",
        "value_type": "boolean",
        "group_name": "backup",
        "description": "是否启用 Git 备份能力",
        "is_public": True,
    },
]
