from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.exceptions import AuthenticationError
from app.models.user import UserAccount
from app.services.auth_service import AuthService


bearer_scheme = HTTPBearer(auto_error=False)


def get_db_session() -> Session:
    """路由依赖：获取数据库会话。"""

    yield from get_session()


def get_client_ip(request: Request) -> str | None:
    """提取客户端 IP；反向代理场景后续可扩展可信代理规则。"""

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> UserAccount:
    """鉴权依赖：校验 Bearer Token 并返回当前用户。"""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("请先登录")
    return AuthService(db, settings).authenticate_token(credentials.credentials)


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """退出登录等场景需要读取原始 Token。"""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("请先登录")
    return credentials.credentials
