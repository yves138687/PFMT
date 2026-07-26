from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import now_utc
from app.models.user import UserSession


class SessionRepository:
    """封装登录会话读写。"""

    def __init__(self, db: Session):
        """绑定当前请求事务使用的数据库会话。"""

        self.db = db

    def create(self, session: UserSession) -> UserSession:
        """创建新的登录会话记录。"""

        self.db.add(session)
        return session

    def get_active(self, session_id: str) -> UserSession | None:
        """查询未过期会话。"""

        stmt = select(UserSession).where(
            UserSession.session_id == session_id,
            UserSession.expires_at > now_utc(),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def touch(self, session: UserSession) -> None:
        """更新会话活跃时间。"""

        session.last_active_at = now_utc()

    def set_show_hidden_enabled(self, session: UserSession, enabled: bool) -> None:
        """更新当前会话是否允许显示隐藏内容。"""

        session.show_hidden_enabled = enabled
        session.last_active_at = now_utc()

    def delete_by_session_id(self, session_id: str) -> None:
        """退出登录时删除会话记录。"""

        self.db.execute(delete(UserSession).where(UserSession.session_id == session_id))
