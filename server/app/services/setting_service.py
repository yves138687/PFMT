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
        setting_value = payload.setting_value
        if setting_key == "ai.providers":
            value_type = "json"
            setting_value = self._merge_ai_providers(
                incoming=payload.setting_value,
                existing_raw=existing.setting_value if existing else None,
                existing_value_type=existing.value_type if existing else "json",
            )
        elif setting_key == "ai.active_provider_id":
            providers_setting = self.repository.get_by_key("ai.providers")
            setting_value = self._normalize_active_ai_provider_id(
                active_provider_id=payload.setting_value,
                providers_raw=providers_setting.setting_value if providers_setting else None,
            )
        setting = SystemSetting(
            setting_key=setting_key,
            setting_value=self.serialize_value(setting_value, value_type),
            value_type=value_type,
            group_name=payload.group_name or (existing.group_name if existing else "custom"),
            description=payload.description if payload.description is not None else (existing.description if existing else None),
            is_public=payload.is_public if payload.is_public is not None else (existing.is_public if existing else False),
            updated_by=updated_by,
        )

        saved = self.repository.upsert(setting)
        if setting_key == "ai.providers":
            self._repair_active_ai_provider_id(
                updated_by=updated_by,
                providers=setting_value if isinstance(setting_value, list) else [],
            )
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

    def _repair_active_ai_provider_id(
        self,
        *,
        updated_by: str,
        providers: list[dict[str, Any]],
    ) -> None:
        """AI 配置列表变化后，修正已删除或已停用的默认模型。"""

        active_setting = self.repository.get_by_key("ai.active_provider_id")
        if active_setting is None:
            return

        normalized = self._normalize_active_ai_provider_id(
            active_provider_id=active_setting.setting_value,
            providers_raw=self.serialize_value(providers, "json"),
        )
        active_setting.setting_value = normalized
        active_setting.updated_by = updated_by

    def _merge_ai_providers(
        self,
        *,
        incoming: Any,
        existing_raw: str | None,
        existing_value_type: str,
    ) -> list[dict[str, Any]]:
        """合并 AI provider 配置，空 api_key 不覆盖已保存密钥。"""

        existing_providers = self._parse_ai_providers(existing_raw, existing_value_type)
        existing_by_id = {
            str(provider.get("id")): provider
            for provider in existing_providers
            if provider.get("id")
        }
        incoming_providers = incoming if isinstance(incoming, list) else []
        merged: list[dict[str, Any]] = []

        for index, provider in enumerate(incoming_providers):
            if not isinstance(provider, dict):
                continue

            provider_id = str(provider.get("id") or f"ai-provider-{index + 1}")
            old_provider = existing_by_id.get(provider_id, {})
            api_key = provider.get("api_key")
            if not isinstance(api_key, str) or not api_key.strip():
                api_key = old_provider.get("api_key")

            merged.append(
                {
                    "id": provider_id,
                    "name": str(provider.get("name") or old_provider.get("name") or "AI 模型"),
                    "provider_type": str(
                        provider.get("provider_type")
                        or old_provider.get("provider_type")
                        or "openai_compatible"
                    ),
                    "base_url": str(provider.get("base_url") or old_provider.get("base_url") or ""),
                    "api_key": api_key if isinstance(api_key, str) and api_key.strip() else None,
                    "model_name": str(provider.get("model_name") or old_provider.get("model_name") or ""),
                    "enabled": self._to_bool(provider.get("enabled", old_provider.get("enabled", True))),
                }
            )

        return merged

    def _normalize_active_ai_provider_id(
        self,
        *,
        active_provider_id: Any,
        providers_raw: str | None,
    ) -> str | None:
        """默认模型不存在时切换到第一个启用配置，否则清空。"""

        requested = str(active_provider_id or "").strip()
        providers = self._parse_ai_providers(providers_raw, "json")
        provider_ids = {
            str(provider.get("id"))
            for provider in providers
            if provider.get("id") and self._to_bool(provider.get("enabled", True))
        }
        if requested and requested in provider_ids:
            return requested

        for provider in providers:
            provider_id = provider.get("id")
            if provider_id and self._to_bool(provider.get("enabled", True)):
                return str(provider_id)
        return None

    @staticmethod
    def _to_bool(value: Any) -> bool:
        """兼容字符串和布尔值形式的配置开关。"""

        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _parse_ai_providers(self, raw_value: str | None, value_type: str) -> list[dict[str, Any]]:
        """安全解析数据库中的 AI provider JSON，异常时返回空列表。"""

        if raw_value is None:
            return []
        try:
            parsed = self.parse_value(raw_value, value_type)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        if not isinstance(parsed, list):
            return []
        return [item for item in parsed if isinstance(item, dict)]

    def _mask_ai_providers(self, providers: Any) -> list[dict[str, Any]]:
        """返回前端可见的 AI provider 列表，并移除完整 API Key。"""

        if not isinstance(providers, list):
            return []

        masked = []
        for provider in providers:
            if not isinstance(provider, dict):
                continue
            api_key = provider.get("api_key")
            item = {**provider, "api_key": None, "api_key_configured": bool(api_key)}
            masked.append(item)
        return masked

    def _to_schema(self, setting: SystemSetting) -> SettingItem:
        """将 ORM 配置模型转换为响应模型。"""

        setting_value = self.parse_value(setting.setting_value, setting.value_type)
        if setting.setting_key == "ai.providers":
            setting_value = self._mask_ai_providers(setting_value)

        return SettingItem(
            setting_key=setting.setting_key,
            setting_value=setting_value,
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
        "setting_key": "document.auto_convert_txt_to_md",
        "setting_value": "false",
        "value_type": "boolean",
        "group_name": "document",
        "description": "上传 txt 文档时是否自动保存为 Markdown",
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
        "setting_key": "ai.providers",
        "setting_value": "[]",
        "value_type": "json",
        "group_name": "ai",
        "description": "AI 模型提供方配置列表",
        "is_public": False,
    },
    {
        "setting_key": "ai.active_provider_id",
        "setting_value": None,
        "value_type": "string",
        "group_name": "ai",
        "description": "当前默认使用的 AI 模型配置",
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
