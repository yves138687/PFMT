from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.compat import router as compat_router
from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import init_database
from app.core.exceptions import AppError
from app.core.logging import RequestLoggingMiddleware, configure_logging
from app.core.seed import seed_application_data
from app.core.security import validate_startup_security
from app.services.file_key_service import FileKeyRotationService
from app.services.storage_integrity_service import StorageIntegrityService


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期：启动时建表并 seed 第一阶段默认数据。"""

    settings = get_settings()
    validate_startup_security(settings)
    storage_integrity = StorageIntegrityService(settings)
    storage_integrity.verify_storage_root()
    init_database(settings)
    seed_application_data(settings)
    storage_integrity.verify_inventory()
    FileKeyRotationService(settings).start_once()
    logging.getLogger("pfmt.app").info("PFMT 后端启动完成")
    yield


def create_app() -> FastAPI:
    """创建 FastAPI 应用，供 uvicorn 和测试复用。"""

    configure_logging()
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    if settings.api_prefix.rstrip("/") != "/api/v1":
        # 兼容子任务与早期合同中的 /api/v1 前缀，前端默认仍使用更短的 /api。
        app.include_router(api_router, prefix="/api/v1")
    app.include_router(compat_router, prefix="/api", tags=["compat"])

    @app.get("/health")
    def health() -> dict[str, str]:
        """健康检查接口，不需要登录。"""

        return {"status": "ok"}

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        """业务异常统一响应。"""

        return JSONResponse(
            status_code=exc.status_code,
            content={"error_code": exc.error_code, "message": exc.message},
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """兜底异常响应，详细堆栈只进入异常日志。"""

        logging.getLogger("pfmt.exception").exception(
            "未处理异常",
            extra={"method": request.method, "path": request.url.path, "status_code": 500},
        )
        return JSONResponse(status_code=500, content={"error_code": "internal_error", "message": "服务器内部错误"})

    return app


app = create_app()
