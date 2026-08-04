from datetime import datetime

from pydantic import BaseModel, Field, field_validator


DocumentFormat = str


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
        """校验可选文件名，避免空名和路径穿越字符进入业务字段。"""

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


class DocumentCreateRequest(BaseModel):
    """创建空白文本、Markdown 或 HTML 文档。"""

    path_id: str = Field(default="root", max_length=64)
    original_name: str = Field(min_length=1, max_length=512)
    document_format: DocumentFormat
    is_hidden: bool = False

    @field_validator("original_name")
    @classmethod
    def validate_original_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("文件名不能为空")
        if "/" in normalized or "\\" in normalized:
            raise ValueError("文件名不能包含路径分隔符")
        return normalized

    @field_validator("document_format")
    @classmethod
    def validate_document_format(cls, value: str) -> str:
        if value not in {"plain_text", "markdown", "html"}:
            raise ValueError("不支持的文档格式")
        return value


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


class DocumentReadResponse(BaseModel):
    """统一文档读取响应，覆盖纯文本、Markdown 和 HTML。"""

    file_id: str
    original_name: str
    mime_type: str | None
    size_bytes: int
    encoding: str = "utf-8"
    document_format: DocumentFormat
    content: str
    editable: bool = True
    rendered_html: str | None = None


class DocumentSaveRequest(BaseModel):
    """保存当前文档内容，格式必须与文件当前格式一致。"""

    content: str = Field(max_length=5 * 1024 * 1024)
    document_format: DocumentFormat

    @field_validator("document_format")
    @classmethod
    def validate_document_format(cls, value: str) -> str:
        if value not in {"plain_text", "markdown", "html"}:
            raise ValueError("不支持的文档格式")
        return value


class DocumentConvertRequest(BaseModel):
    """将当前文档转换为新文件。"""

    target_format: DocumentFormat
    target_name: str | None = Field(default=None, min_length=1, max_length=512)

    @field_validator("target_format")
    @classmethod
    def validate_target_format(cls, value: str) -> str:
        if value not in {"plain_text", "markdown", "html"}:
            raise ValueError("不支持的目标格式")
        return value

    @field_validator("target_name")
    @classmethod
    def validate_target_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("目标文件名不能为空")
        if "/" in normalized or "\\" in normalized:
            raise ValueError("目标文件名不能包含路径分隔符")
        return normalized


class DocumentMergeRequest(BaseModel):
    """将多个文档合并为新文件。"""

    file_ids: list[str] = Field(min_length=2, max_length=50)
    target_format: DocumentFormat = "markdown"
    target_name: str | None = Field(default=None, min_length=1, max_length=512)

    @field_validator("file_ids")
    @classmethod
    def validate_file_ids(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if len(normalized) < 2:
            raise ValueError("至少选择两个文档")
        return normalized

    @field_validator("target_format")
    @classmethod
    def validate_target_format(cls, value: str) -> str:
        if value not in {"plain_text", "markdown", "html"}:
            raise ValueError("不支持的目标格式")
        return value

    @field_validator("target_name")
    @classmethod
    def validate_target_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("目标文件名不能为空")
        if "/" in normalized or "\\" in normalized:
            raise ValueError("目标文件名不能包含路径分隔符")
        return normalized


class FileExportRequest(BaseModel):
    """批量导出文件请求。"""

    file_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("file_ids")
    @classmethod
    def validate_file_ids(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            file_id = item.strip()
            if not file_id or file_id in seen:
                continue
            seen.add(file_id)
            normalized.append(file_id)
        if not normalized:
            raise ValueError("至少选择一个文件")
        return normalized


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
        """校验标签名，统一去除首尾空白并限制长度。"""

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
        """清洗标签名列表，去重并过滤空标签。"""

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
