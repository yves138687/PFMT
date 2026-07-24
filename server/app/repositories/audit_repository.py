from sqlalchemy.orm import Session

from app.models.audit import AuditLog


class AuditRepository:
    """封装审计日志写入，审计日志原则上只增不改不删。"""

    def __init__(self, db: Session):
        self.db = db

    def create(self, audit_log: AuditLog) -> AuditLog:
        """写入一条审计日志。"""

        self.db.add(audit_log)
        return audit_log
