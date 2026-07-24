from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


PathType = Literal["normal", "private"]


class PathCreateRequest(BaseModel):
    """创建目录请求。"""

    path_name: str = Field(min_length=1, max_length=255)
    parent_path_id: str = Field(default="root", max_length=64)
    path_type: PathType = "normal"
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


class PathRead(BaseModel):
    """目录基础信息响应。"""

    path_id: str
    parent_path_id: str | None
    path_name: str
    path_type: PathType
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
