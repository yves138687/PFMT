class AppError(Exception):
    """业务异常基类，路由层会转换为统一 JSON 响应。"""

    status_code = 400
    error_code = "bad_request"

    def __init__(self, message: str, *, status_code: int | None = None, error_code: str | None = None):
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code
        super().__init__(message)


class AuthenticationError(AppError):
    status_code = 401
    error_code = "authentication_failed"


class PermissionDeniedError(AppError):
    status_code = 403
    error_code = "permission_denied"


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"


class ConflictError(AppError):
    status_code = 409
    error_code = "conflict"


class UnsupportedFileTypeError(AppError):
    status_code = 415
    error_code = "unsupported_file_type"


class PayloadTooLargeError(AppError):
    status_code = 413
    error_code = "payload_too_large"
