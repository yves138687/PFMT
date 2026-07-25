from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class FileTagItem(BaseModel):
    """文件标签响应。"""

    tag_id: str
    tag_name: str
    tag_color: str | None = None


class FileUploadResponse(BaseModel):
    """文件上传后返回的元数据，不暴露物理绝对路径。"""

    file_id: str
    path_id: str
    original_name: str
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
    summary_content: str | None = None
    tags: list[FileTagItem] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime | None = None


class FileDetailResponse(FileListItem):
    """文件详情响应，补充业务逻辑路径，仍不暴露底层存储信息。"""

    logical_path: str
    checksum_sha256: str | None = None


class FileUpdateRequest(BaseModel):
    """更新文件元数据；不修改文件本体和存储对象。"""

    original_name: str | None = Field(default=None, min_length=1, max_length=512)
    remark: str | None = Field(default=None, max_length=2000)
    summary_content: str | None = Field(default=None, max_length=8000)
    is_hidden: bool | None = None

    @field_validator("original_name")
    @classmethod
    def validate_original_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("文件名不能为空")
        if "/" in normalized or "\\" in normalized:
            raise ValueError("文件名不能包含路径分隔符")
        return normalized


FileRemarkUpdateRequest = FileUpdateRequest


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


class TextReadResponse(BaseModel):
    """纯文本读取响应，content 为解密后的文本内容。"""

    file_id: str
    original_name: str
    mime_type: str | None
    size_bytes: int
    encoding: str = "utf-8"
    content: str


class FilePreviewTokenResponse(BaseModel):
    """短时效文件预览 Token 响应。"""

    file_id: str
    preview_url: str
    expires_at: datetime


class FileTagCreateRequest(BaseModel):
    """创建或复用标签。"""

    tag_name: str = Field(min_length=1, max_length=128)
    tag_color: str | None = Field(default=None, max_length=32)

    @field_validator("tag_name")
    @classmethod
    def validate_tag_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("标签名不能为空")
        return normalized


class FileTagsUpdateRequest(BaseModel):
    """替换文件标签集合。"""

    tag_names: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("tag_names")
    @classmethod
    def validate_tag_names(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            tag_name = item.strip()
            if not tag_name:
                continue
            lowered = tag_name.lower()
            if lowered in seen:
                continue
            if len(tag_name) > 128:
                raise ValueError("标签名不能超过 128 个字符")
            seen.add(lowered)
            normalized.append(tag_name)
        return normalized


class FileSearchResponse(BaseModel):
    """元数据搜索响应。"""

    items: list[FileDetailResponse]
    total: int
