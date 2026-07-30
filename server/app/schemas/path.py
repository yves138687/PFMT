from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class PathCreateRequest(BaseModel):
    """创建目录请求。"""

    path_name: str = Field(min_length=1, max_length=255)
    parent_path_id: str = Field(default="root", max_length=64)
    description: str | None = None
    is_hidden: bool = False

    @field_validator("path_name")
    @classmethod
    def validate_path_name(cls, value: str) -> str:
        """目录名不能包含路径分隔符，避免绕过父子目录计算。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("目录名不能为空")
        if "/" in normalized or "\\" in normalized:
            raise ValueError("目录名不能包含路径分隔符")
        return normalized


class PathMoveRequest(BaseModel):
    """移动目录请求。"""

    parent_path_id: str = Field(max_length=64)


class PathUpdateRequest(BaseModel):
    """更新目录元数据。"""

    path_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_hidden: bool | None = None

    @field_validator("path_name")
    @classmethod
    def validate_path_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("目录名不能为空")
        if "/" in normalized or "\\" in normalized:
            raise ValueError("目录名不能包含路径分隔符")
        return normalized


class PathRead(BaseModel):
    """目录基础信息响应。"""

    path_id: str
    parent_path_id: str | None
    path_name: str
    path_level: int
    sort_index: int
    full_path: str
    description: str | None
    is_hidden: bool
    status: str
    created_at: datetime
    updated_at: datetime


class PathTreeNode(PathRead):
    """目录树节点响应。"""

    children: list["PathTreeNode"] = Field(default_factory=list)
