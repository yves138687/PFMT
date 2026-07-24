import jwt
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
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

    def __init__(self, db: Session, settings: Settings):
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

        user = self.user_repository.get_by_username(username)
        if user is None or user.status != "active" or not verify_password(password, user.password_hash):
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
        return user

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
