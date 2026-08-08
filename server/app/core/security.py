import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import Settings


password_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__type="ID",
)


def now_utc() -> datetime:
    """返回无时区 UTC 时间，匹配 SQLite DATETIME 的轻量存储方式。"""

    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    """使用 Argon2id 哈希登录密码。"""

    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与 Argon2id 哈希是否匹配。"""

    return password_context.verify(password, password_hash)


def hash_token(token: str) -> str:
    """只把 Token 摘要写入会话表，避免原始凭据落库。"""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    *,
    settings: Settings,
    user_id: str,
    session_id: str,
    expires_delta: timedelta | None = None,
) -> tuple[str, datetime]:
    """签发 JWT 登录态，sub 保存业务用户 ID，sid 保存会话 ID。"""

    expires_at = now_utc() + (expires_delta or timedelta(minutes=settings.jwt_access_token_minutes))
    payload: dict[str, Any] = {
        "sub": user_id,
        "sid": session_id,
        "exp": expires_at.replace(tzinfo=timezone.utc),
        "iat": now_utc().replace(tzinfo=timezone.utc),
    }
    token = jwt.encode(payload, settings.effective_jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_access_token(settings: Settings, token: str) -> dict[str, Any]:
    """解析 JWT；调用方负责把异常转换为认证失败。"""

    return jwt.decode(token, settings.effective_jwt_secret, algorithms=[settings.jwt_algorithm])


def validate_startup_security(settings: Settings) -> None:
    """启动期安全校验，避免生产或加密场景使用隐式弱配置。"""

    if not settings.is_production:
        return

    if settings.effective_jwt_secret == "pfmt-dev-change-me" or len(settings.effective_jwt_secret) < 32:
        raise RuntimeError("生产环境必须配置不少于 32 字符的 PFMT_JWT_SECRET_KEY")
    if settings.admin_password == "admin123456" or len(settings.admin_password) < 12:
        raise RuntimeError("生产环境必须配置非默认且不少于 12 字符的 PFMT_ADMIN_PASSWORD")
