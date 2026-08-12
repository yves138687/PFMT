from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


SettingValueType = Literal["string", "boolean", "number", "json"]


class SettingItem(BaseModel):
    """系统配置响应项，setting_value 已按 value_type 转成业务值。"""

    setting_key: str
    setting_value: Any
    value_type: SettingValueType
    group_name: str
    description: str | None = None
    is_public: bool
    updated_at: datetime
    updated_by: str | None = None


class SettingUpdateRequest(BaseModel):
    """系统配置写入请求，支持更新既有配置或预留新配置。"""

    setting_value: Any
    value_type: SettingValueType | None = None
    group_name: str | None = Field(default=None, max_length=64)
    description: str | None = None
    is_public: bool | None = None


class AiProviderVerifyRequest(BaseModel):
    """验证 AI provider 可用性；api_key 为空时允许后端尝试使用已保存密钥。"""

    id: str | None = Field(default=None, max_length=128)
    name: str | None = Field(default=None, max_length=128)
    provider_type: str = Field(default="openai_compatible", max_length=64)
    base_url: str = Field(max_length=512)
    api_key: str | None = Field(default=None, max_length=4096)
    model_name: str = Field(max_length=128)


class AiProviderVerifyResponse(BaseModel):
    ok: bool
    message: str
    model_name: str | None = None
