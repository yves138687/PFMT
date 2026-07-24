from datetime import datetime

from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    """文件上传后返回的元数据，不暴露物理绝对路径。"""

    file_id: str
    path_id: str
    original_name: str
    storage_object_name: str
    storage_provider: str
    mime_type: str | None
    file_ext: str | None
    file_type: str
    size_bytes: int
    checksum_sha256: str | None
    encryption_enabled: bool
    key_wrap_version: str | None
    is_hidden: bool
    visibility_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime | None = None


class MarkdownReadResponse(BaseModel):
    """Markdown 读取响应，content 为解密后的文本内容。"""

    file_id: str
    original_name: str
    mime_type: str | None
    size_bytes: int
    encoding: str = "utf-8"
    content: str
