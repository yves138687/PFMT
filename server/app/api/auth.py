from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_bearer_token, get_client_ip, get_current_user, get_db_session
from app.core.config import Settings, get_settings
from app.models.user import UserAccount
from app.schemas.auth import (
    HiddenContentPasswordRequest,
    HiddenContentPasswordResponse,
    HiddenContentSessionRequest,
    HiddenContentSessionResponse,
    LoginRequest,
    TokenResponse,
    UserProfile,
)
from app.services.auth_service import AuthService


router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> TokenResponse:
    """单用户登录接口，成功后返回 JWT。"""

    user_agent = request.headers.get("user-agent")
    return AuthService(db, settings).login(
        username=payload.username,
        password=payload.password,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@router.get("/me", response_model=UserProfile)
def me(current_user: UserAccount = Depends(get_current_user)) -> UserProfile:
    """读取当前登录用户信息。"""

    return AuthService._to_profile(current_user)


@router.get("/hidden-content", response_model=HiddenContentSessionResponse)
def get_hidden_content_session(current_user: UserAccount = Depends(get_current_user)) -> HiddenContentSessionResponse:
    """读取当前登录会话的隐藏内容显示状态。"""

    enabled = bool(getattr(current_user, "_pfmt_show_hidden_enabled", False))
    return HiddenContentSessionResponse(show_hidden_enabled=enabled)


@router.put("/hidden-content", response_model=HiddenContentSessionResponse)
def set_hidden_content_session(
    payload: HiddenContentSessionRequest,
    token: str = Depends(get_bearer_token),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> HiddenContentSessionResponse:
    """当前会话显式开启/关闭隐藏内容显示；开启时若已配置二次验证码需携带 password。"""

    enabled = AuthService(db, settings).set_hidden_content_enabled(
        token=token,
        current_user=current_user,
        enabled=payload.enabled,
        password=payload.password,
        client_ip=client_ip,
    )
    return HiddenContentSessionResponse(show_hidden_enabled=enabled)


@router.put("/hidden-content/password", response_model=HiddenContentPasswordResponse)
def set_hidden_content_password(
    payload: HiddenContentPasswordRequest,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> HiddenContentPasswordResponse:
    """设置或清除隐藏内容二次验证码；已配置时需先通过当前验证码校验。"""

    configured = AuthService(db, settings).set_hidden_content_password(
        current_user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        client_ip=client_ip,
    )
    return HiddenContentPasswordResponse(configured=configured)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    token: str = Depends(get_bearer_token),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    client_ip: str | None = Depends(get_client_ip),
) -> None:
    """退出登录并删除会话。"""

    AuthService(db, settings).logout(token=token, current_user=current_user, client_ip=client_ip)
