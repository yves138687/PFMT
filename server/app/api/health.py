from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["健康检查"])


@router.get("")
def health() -> dict[str, str]:
    """轻量健康检查接口，用于本地启动和部署探活。"""

    return {"status": "ok"}
