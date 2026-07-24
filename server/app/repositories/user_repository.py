from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import now_utc
from app.models.user import UserAccount


class UserRepository:
    """封装用户账号查询与写入。"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_username(self, username: str) -> UserAccount | None:
        """按登录名查询用户。"""

        stmt = select(UserAccount).where(UserAccount.username == username)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_user_id(self, user_id: str) -> UserAccount | None:
        """按业务用户 ID 查询用户。"""

        stmt = select(UserAccount).where(UserAccount.user_id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, user: UserAccount) -> UserAccount:
        """创建账号，具体提交由 Service 控制。"""

        self.db.add(user)
        return user

    def mark_login_success(self, user: UserAccount) -> None:
        """更新最后登录时间。"""

        user.last_login_at = now_utc()
        user.updated_at = now_utc()
