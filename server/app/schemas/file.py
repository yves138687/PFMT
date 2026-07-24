from datetime import datetime

from pydantic import BaseModel, Field


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


class FileListItem(BaseModel):
    """文件列表展示所需元数据，不包含存储对象名和物理路径。"""

    file_id: str
    path_id: str
    original_name: str
    mime_type: str | None
    file_ext: str | None
    file_type: str
    size_bytes: int
    encryption_enabled: bool
    is_hidden: bool
    visibility_type: str
    status: str
    remark: str | None = None
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime | None = None


class FileDetailResponse(FileListItem):
    """文件详情响应，补充业务逻辑路径，仍不暴露底层存储信息。"""

    logical_path: str
    checksum_sha256: str | None = None


class FileRemarkUpdateRequest(BaseModel):
    """更新文件备注；备注用于业务描述，不参与文件本体存储。"""

    remark: str | None = Field(default=None, max_length=2000)


class FileMoveRequest(BaseModel):
    """移动文件请求，只调整业务目录归属。"""

    path_id: str = Field(max_length=64)


class MarkdownReadResponse(BaseModel):
    """Markdown 读取响应，content 为解密后的文本内容。"""

    file_id: str
    original_name: str
    mime_type: str | None
    size_bytes: int
    encoding: str = "utf-8"
    content: str
