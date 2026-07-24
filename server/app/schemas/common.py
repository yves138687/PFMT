from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """统一错误响应结构。"""

    error_code: str
    message: str
