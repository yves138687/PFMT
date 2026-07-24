import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.repositories.audit_repository import AuditRepository
from app.utils.ids import new_business_id


class AuditService:
    """审计服务，负责把关键业务行为写入 audit_log 并输出业务日志。"""

    def __init__(self, db: Session):
        self.db = db
        self.repository = AuditRepository(db)
        self.logger = logging.getLogger("pfmt.business")

    def record(
        self,
        *,
        user_id: str | None,
        action_type: str,
        target_type: str | None = None,
        target_id: str | None = None,
        result: str = "success",
        detail: dict[str, Any] | str | None = None,
        client_ip: str | None = None,
    ) -> AuditLog:
        """记录审计日志；detail 只放非敏感业务摘要。"""

        detail_text: str | None
        if isinstance(detail, dict):
            detail_text = json.dumps(detail, ensure_ascii=False, separators=(",", ":"))
        else:
            detail_text = detail

        audit_log = AuditLog(
            log_id=new_business_id("audit"),
            user_id=user_id,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            action_result=result,
            detail=detail_text,
            client_ip=client_ip,
        )
        self.repository.create(audit_log)
        self.logger.info(
            "业务操作",
            extra={
                "action": action_type,
                "target_type": target_type,
                "target_id": target_id,
                "result": result,
                "client_ip": client_ip,
            },
        )
        return audit_log
