from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """集中读取后端环境配置，并把相对路径归一到仓库根目录。"""

    model_config = SettingsConfigDict(
        env_prefix="PFMT_",
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "server" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "PFMT"
    env: str = "dev"
    api_prefix: str = "/api"
    database_url: str | None = None
    storage_root: str | None = None
    jwt_secret_key: str = "pfmt-dev-change-me"
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 480
    admin_username: str = "admin"
    admin_password: str = "admin123456"
    admin_display_name: str = "管理员"
    file_master_key: str | None = None
    upload_chunk_size: int = 1024 * 1024
    markdown_read_max_bytes: int = 5 * 1024 * 1024
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    file_encryption_enabled: bool = True
    hidden_feature_enabled: bool = True
    show_hidden_by_default: bool = False
    ai_enabled: bool = False
    backup_enabled: bool = False

    @property
    def effective_jwt_secret(self) -> str:
        """兼容 PFMT_JWT_SECRET 与 PFMT_JWT_SECRET_KEY 两种环境变量命名。"""

        if self.jwt_secret_key != "pfmt-dev-change-me":
            return self.jwt_secret_key
        return self.jwt_secret or self.jwt_secret_key

    @property
    def storage_root_path(self) -> Path:
        """返回文件存储根目录，支持环境变量里写相对路径。"""

        raw_path = self.storage_root or str(PROJECT_ROOT / "storage")
        path = Path(raw_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    @property
    def resolved_database_url(self) -> str:
        """返回稳定的数据库 URL，避免不同启动目录导致 SQLite 文件漂移。"""

        if not self.database_url:
            db_path = self.storage_root_path / "pfmt.sqlite3"
            return f"sqlite:///{db_path.as_posix()}"

        sqlite_prefix = "sqlite:///"
        if self.database_url.startswith(sqlite_prefix) and not self.database_url.startswith(
            "sqlite:////"
        ):
            sqlite_path = self.database_url.removeprefix(sqlite_prefix)
            if sqlite_path and sqlite_path != ":memory:":
                path = Path(sqlite_path)
                if not path.is_absolute():
                    path = PROJECT_ROOT / path
                return f"sqlite:///{path.as_posix()}"

        return self.database_url

    @property
    def cors_origin_list(self) -> list[str]:
        """将逗号分隔的 CORS 配置转换为 FastAPI 可用列表。"""

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """缓存配置对象，测试中可通过 cache_clear 后重新加载环境变量。"""

    return Settings()
