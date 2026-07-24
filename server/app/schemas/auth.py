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


class TokenResponse(BaseModel):
    """登录成功后的 JWT 响应。"""

    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserProfile
