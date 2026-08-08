from collections.abc import Generator
import logging
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings, get_settings


class Base(DeclarativeBase):
    """SQLAlchemy 2.x 声明式模型基类。"""


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _sqlite_path_from_url(database_url: str) -> Path | None:
    """从 SQLite URL 中提取数据库文件路径，用于启动前创建父目录。"""

    prefix = "sqlite:///"
    if not database_url.startswith(prefix) or database_url == "sqlite:///:memory:":
        return None
    raw_path = database_url.removeprefix(prefix)
    return Path(raw_path)


def get_engine(settings: Settings | None = None) -> Engine:
    """创建或复用全局数据库引擎。"""

    global _engine
    if _engine is not None:
        return _engine

    settings = settings or get_settings()
    database_url = settings.resolved_database_url
    sqlite_path = _sqlite_path_from_url(database_url)
    connect_args: dict[str, object] = {}
    if sqlite_path is not None:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        connect_args["check_same_thread"] = False

    _engine = create_engine(database_url, connect_args=connect_args, future=True)

    if sqlite_path is not None:

        @event.listens_for(_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            # SQLite 默认不强制外键，这里与 scripts/db/schema.sql 的 PRAGMA 保持一致。
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return _engine


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    """创建或复用 Session 工厂，所有 Repository 通过它拿数据库会话。"""

    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(settings), autoflush=False, expire_on_commit=False
        )
    return _session_factory


def get_session() -> Generator[Session, None, None]:
    """FastAPI 依赖：为单次请求提供数据库会话。"""

    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def init_database(settings: Settings | None = None) -> None:
    """初始化数据库表结构；第一阶段用 create_all，后续可替换为 Alembic。"""

    from app import models  # noqa: F401

    engine = get_engine(settings)
    Base.metadata.create_all(bind=engine)
    _patch_sqlite_schema(engine)


def _patch_sqlite_schema(engine: Engine) -> None:
    """为开发期已有 SQLite 库补齐轻量字段，避免 create_all 无法更新旧表。"""

    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as connection:
        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(file_info)")).all()
        }
        if columns and "remark" not in columns:
            connection.execute(text("ALTER TABLE file_info ADD COLUMN remark TEXT"))
            logging.getLogger("pfmt.app").info("SQLite file_info.remark 字段补列完成")
        if columns and "summary_content" not in columns:
            connection.execute(text("ALTER TABLE file_info ADD COLUMN summary_content TEXT"))
        if columns and "summary_source" not in columns:
            connection.execute(text("ALTER TABLE file_info ADD COLUMN summary_source VARCHAR(32)"))
        if columns and "summary_updated_at" not in columns:
            connection.execute(text("ALTER TABLE file_info ADD COLUMN summary_updated_at DATETIME"))
        if columns and "key_id" not in columns:
            connection.execute(text("ALTER TABLE file_info ADD COLUMN key_id VARCHAR(64)"))
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS idx_file_info_encryption_key_status ON file_info(encryption_enabled, key_id, status)")
        )

        session_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(user_session)")).all()
        }
        if session_columns and "show_hidden_enabled" not in session_columns:
            connection.execute(
                text("ALTER TABLE user_session ADD COLUMN show_hidden_enabled BOOLEAN NOT NULL DEFAULT 0")
            )

        path_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(file_path)")).all()
        }
        if path_columns and "storage_name" not in path_columns:
            connection.execute(text("ALTER TABLE file_path ADD COLUMN storage_name VARCHAR(64)"))
        if path_columns and "storage_path" not in path_columns:
            connection.execute(text("ALTER TABLE file_path ADD COLUMN storage_path TEXT"))
            connection.execute(text("UPDATE file_path SET storage_path = 'data' WHERE path_id = 'root'"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_file_path_storage_path ON file_path(storage_path)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_file_path_storage_path ON file_path(storage_path)"))

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS file_tag (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag_id VARCHAR(64) NOT NULL,
                    tag_name VARCHAR(128) NOT NULL,
                    tag_color VARCHAR(32),
                    status VARCHAR(32) NOT NULL DEFAULT 'active',
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    CONSTRAINT ck_file_tag_status CHECK (status IN ('active', 'deleted')),
                    CONSTRAINT uq_file_tag_tag_id UNIQUE (tag_id),
                    CONSTRAINT uq_file_tag_tag_name UNIQUE (tag_name)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS file_tag_rel (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id VARCHAR(64) NOT NULL,
                    tag_id VARCHAR(64) NOT NULL,
                    created_at DATETIME NOT NULL,
                    CONSTRAINT uq_file_tag_rel_file_tag UNIQUE (file_id, tag_id),
                    FOREIGN KEY (file_id) REFERENCES file_info(file_id) ON DELETE CASCADE ON UPDATE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES file_tag(tag_id) ON DELETE CASCADE ON UPDATE CASCADE
                )
                """
            )
        )
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_file_tag_status ON file_tag(status)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_file_tag_rel_file_id ON file_tag_rel(file_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_file_tag_rel_tag_id ON file_tag_rel(tag_id)"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS file_key (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_id VARCHAR(64) NOT NULL,
                    key_material TEXT NOT NULL,
                    key_hash VARCHAR(128) NOT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'active_completed',
                    is_active BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL,
                    activated_at DATETIME,
                    completed_at DATETIME,
                    expired_at DATETIME,
                    CONSTRAINT ck_file_key_status CHECK (status IN ('expired', 'active_rotating', 'active_completed')),
                    CONSTRAINT uq_file_key_key_id UNIQUE (key_id)
                )
                """
            )
        )
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_file_key_key_id ON file_key(key_id)"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_file_key_one_active ON file_key(is_active) WHERE is_active = 1"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_file_key_active ON file_key(is_active, status)"))


def reset_database_state() -> None:
    """测试辅助：丢弃缓存的引擎和 Session 工厂。"""

    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
