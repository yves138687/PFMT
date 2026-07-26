from datetime import datetime, timedelta

import jwt
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, TooManyRequestsError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_token,
    now_utc,
    verify_password,
)
from app.models.user import UserAccount, UserSession
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse, UserProfile
from app.services.audit_service import AuditService
from app.utils.ids import new_business_id


class AuthService:
    """认证服务，负责单用户登录、JWT 签发与会话校验。"""

    _failed_login_attempts: dict[str, list[datetime]] = {}
    _login_locks: dict[str, datetime] = {}

    def __init__(self, db: Session, settings: Settings):
        """初始化认证服务依赖的仓储、配置和审计服务。"""

        self.db = db
        self.settings = settings
        self.user_repository = UserRepository(db)
        self.session_repository = SessionRepository(db)
        self.audit_service = AuditService(db)

    def login(
        self,
        *,
        username: str,
        password: str,
        client_ip: str | None,
        user_agent: str | None,
    ) -> TokenResponse:
        """校验账号密码，成功后签发 JWT 并落会话摘要。"""

        rate_limit_key = self._rate_limit_key(username=username, client_ip=client_ip)
        self._ensure_login_allowed(rate_limit_key)
        user = self.user_repository.get_by_username(username)
        if user is None or user.status != "active" or not verify_password(password, user.password_hash):
            self._record_failed_login_attempt(rate_limit_key)
            self.audit_service.record(
                user_id=user.user_id if user else None,
                action_type="login",
                target_type="user",
                target_id=user.user_id if user else None,
                result="failed",
                detail={"reason": "invalid_credentials"},
                client_ip=client_ip,
            )
            self.db.commit()
            raise AuthenticationError("用户名或密码错误")

        self._clear_failed_login_attempts(rate_limit_key)
        session_id = new_business_id("session")
        token, expires_at = create_access_token(
            settings=self.settings,
            user_id=user.user_id,
            session_id=session_id,
        )
        self.session_repository.create(
            UserSession(
                session_id=session_id,
                user_id=user.user_id,
                access_token=hash_token(token),
                client_ip=client_ip,
                user_agent=user_agent,
                expires_at=expires_at,
                last_active_at=now_utc(),
            )
        )
        self.user_repository.mark_login_success(user)
        self.audit_service.record(
            user_id=user.user_id,
            action_type="login",
            target_type="user",
            target_id=user.user_id,
            result="success",
            client_ip=client_ip,
        )
        self.db.commit()
        self.db.refresh(user)
        return TokenResponse(
            access_token=token,
            expires_at=expires_at,
            user=self._to_profile(user),
        )

    def authenticate_token(self, token: str) -> UserAccount:
        """校验 JWT 与会话摘要，返回当前用户。"""

        try:
            payload = decode_access_token(self.settings, token)
        except jwt.PyJWTError as exc:
            raise AuthenticationError("登录态无效或已过期") from exc

        user_id = payload.get("sub")
        session_id = payload.get("sid")
        if not isinstance(user_id, str) or not isinstance(session_id, str):
            raise AuthenticationError("登录态无效或已过期")

        session = self.session_repository.get_active(session_id)
        if session is None or session.user_id != user_id or session.access_token != hash_token(token):
            raise AuthenticationError("登录态无效或已过期")

        user = self.user_repository.get_by_user_id(user_id)
        if user is None or user.status != "active":
            raise AuthenticationError("登录态无效或已过期")

        self.session_repository.touch(session)
        setattr(user, "_pfmt_session_id", session.session_id)
        setattr(user, "_pfmt_show_hidden_enabled", bool(session.show_hidden_enabled))
        return user

    def set_hidden_content_enabled(self, *, token: str, current_user: UserAccount, enabled: bool) -> bool:
        """更新当前登录会话的隐藏内容显示授权。"""

        try:
            payload = decode_access_token(self.settings, token)
        except jwt.PyJWTError as exc:
            raise AuthenticationError("登录态无效或已过期") from exc

        session_id = payload.get("sid")
        if not isinstance(session_id, str):
            raise AuthenticationError("登录态无效或已过期")

        session = self.session_repository.get_active(session_id)
        if session is None or session.user_id != current_user.user_id or session.access_token != hash_token(token):
            raise AuthenticationError("登录态无效或已过期")

        self.session_repository.set_show_hidden_enabled(session, enabled)
        self.db.commit()
        return enabled

    def logout(self, *, token: str, current_user: UserAccount, client_ip: str | None) -> None:
        """退出登录，删除当前会话记录。"""

        try:
            payload = decode_access_token(self.settings, token)
            session_id = payload.get("sid")
            if isinstance(session_id, str):
                self.session_repository.delete_by_session_id(session_id)
        except jwt.PyJWTError:
            pass

        self.audit_service.record(
            user_id=current_user.user_id,
            action_type="logout",
            target_type="user",
            target_id=current_user.user_id,
            result="success",
            client_ip=client_ip,
        )
        self.db.commit()

    def _rate_limit_key(self, *, username: str, client_ip: str | None) -> str:
        """生成登录限流键，按用户名和客户端 IP 聚合失败次数。"""

        return f"{username.strip().lower()}|{client_ip or 'unknown'}"

    def _ensure_login_allowed(self, key: str) -> None:
        """检查登录失败锁定窗口，锁定期间拒绝继续认证。"""

        now = now_utc()
        locked_until = self._login_locks.get(key)
        if locked_until is not None and locked_until > now:
            raise TooManyRequestsError("登录失败次数过多，请稍后再试")
        if locked_until is not None:
            self._login_locks.pop(key, None)

    def _record_failed_login_attempt(self, key: str) -> None:
        """记录一次登录失败，达到阈值后进入临时锁定。"""

        now = now_utc()
        window_started_at = now - timedelta(minutes=self.settings.login_rate_limit_window_minutes)
        attempts = [
            attempt_at
            for attempt_at in self._failed_login_attempts.get(key, [])
            if attempt_at >= window_started_at
        ]
        attempts.append(now)
        self._failed_login_attempts[key] = attempts
        if len(attempts) >= self.settings.login_rate_limit_attempts:
            self._login_locks[key] = now + timedelta(minutes=self.settings.login_rate_limit_lock_minutes)

    def _clear_failed_login_attempts(self, key: str) -> None:
        """登录成功后清除该限流键的失败记录。"""

        self._failed_login_attempts.pop(key, None)
        self._login_locks.pop(key, None)

    @staticmethod
    def _to_profile(user: UserAccount) -> UserProfile:
        """将用户模型转换为安全的响应信息。"""

        return UserProfile(
            user_id=user.user_id,
            username=user.username,
            display_name=user.display_name,
            status=user.status,
            last_login_at=user.last_login_at,
        )
