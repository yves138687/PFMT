import json
import logging
import sys
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    """将运行日志输出为 JSON，方便后续被日志系统采集。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None) or request_id_var.get()
        if request_id:
            payload["request_id"] = request_id

        for key in (
            "method",
            "path",
            "status_code",
            "duration_ms",
            "action",
            "target_type",
            "target_id",
            "result",
            "client_ip",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """配置结构化日志；不记录请求体，避免密码、Token 等敏感信息入日志。"""

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if root_logger.handlers:
        for handler in root_logger.handlers:
            handler.setFormatter(JsonFormatter())
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """记录请求方法、路径、状态码和耗时，不触碰请求体。"""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid4().hex
        token = request_id_var.set(request_id)
        started_at = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["x-request-id"] = request_id
            return response
        except Exception:
            logging.getLogger("pfmt.exception").exception(
                "请求处理异常",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "client_ip": request.client.host if request.client else None,
                },
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logging.getLogger("pfmt.request").info(
                "请求完成",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": request.client.host if request.client else None,
                },
            )
            request_id_var.reset(token)
