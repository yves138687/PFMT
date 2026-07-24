from uuid import uuid4


def new_business_id(prefix: str) -> str:
    """生成对外暴露的业务 ID，避免使用数据库自增主键。"""

    return f"{prefix}_{uuid4().hex}"
