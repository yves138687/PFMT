from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求，密码只用于校验，不进入日志和响应。"""

    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class UserProfile(BaseModel):
    """当前登录用户的安全展示信息。"""

    user_id: str
    username: str
    display_name: str
    status: str
    last_login_at: datetime | None = None


class HiddenContentSessionRequest(BaseModel):
    """当前登录会话的隐藏内容显示开关；开启时若已配置二次验证码需携带 password。"""

    enabled: bool
    password: str | None = Field(default=None, max_length=256)


class HiddenContentSessionResponse(BaseModel):
    """当前登录会话是否允许读取隐藏内容。"""

    show_hidden_enabled: bool


class HiddenContentPasswordRequest(BaseModel):
    """设置或清除隐藏内容二次验证码；已配置时需先通过 current_password 校验。"""

    current_password: str | None = Field(default=None, max_length=256)
    new_password: str = Field(default="", max_length=256)


class HiddenContentPasswordResponse(BaseModel):
    """当前是否已配置独立的隐藏内容二次验证码。"""

    configured: bool


class TokenResponse(BaseModel):
    """登录成功后的 JWT 响应。"""

    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserProfile
