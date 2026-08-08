PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS user_account (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    username TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    last_login_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id),
    UNIQUE (username)
);

CREATE TABLE IF NOT EXISTS user_session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    client_ip TEXT,
    user_agent TEXT,
    expires_at DATETIME NOT NULL,
    last_active_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (session_id),
    FOREIGN KEY (user_id) REFERENCES user_account(user_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS file_path (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path_id TEXT NOT NULL,
    parent_path_id TEXT,
    path_name TEXT NOT NULL,
    storage_name TEXT,
    storage_path TEXT NOT NULL,
    path_type TEXT NOT NULL DEFAULT 'normal' CHECK (path_type IN ('normal', 'private')),
    path_level INTEGER NOT NULL DEFAULT 0 CHECK (path_level >= 0),
    sort_index INTEGER NOT NULL DEFAULT 0,
    full_path TEXT NOT NULL,
    description TEXT,
    is_hidden INTEGER NOT NULL DEFAULT 0 CHECK (is_hidden IN (0, 1)),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'deleted')),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (path_id),
    UNIQUE (full_path),
    UNIQUE (storage_path),
    FOREIGN KEY (parent_path_id) REFERENCES file_path(path_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS file_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT NOT NULL,
    path_id TEXT NOT NULL,
    original_name TEXT NOT NULL,
    storage_object_name TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    storage_provider TEXT NOT NULL DEFAULT 'local',
    mime_type TEXT,
    file_ext TEXT,
    file_type TEXT NOT NULL DEFAULT 'other' CHECK (file_type IN ('text', 'image', 'video', 'pdf', 'audio', 'other')),
    size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
    checksum_sha256 TEXT,
    encryption_enabled INTEGER NOT NULL DEFAULT 1 CHECK (encryption_enabled IN (0, 1)),
    key_wrap_version TEXT,
    key_id TEXT,
    summary_content TEXT,
    summary_source TEXT CHECK (summary_source IN ('manual', 'ai')),
    summary_updated_at DATETIME,
    is_hidden INTEGER NOT NULL DEFAULT 0 CHECK (is_hidden IN (0, 1)),
    visibility_type TEXT NOT NULL DEFAULT 'normal' CHECK (visibility_type IN ('normal', 'private')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'deleted', 'archived')),
    created_by TEXT,
    updated_by TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at DATETIME,
    UNIQUE (file_id),
    UNIQUE (storage_object_name),
    UNIQUE (storage_path),
    FOREIGN KEY (path_id) REFERENCES file_path(path_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    FOREIGN KEY (created_by) REFERENCES user_account(user_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,
    FOREIGN KEY (updated_by) REFERENCES user_account(user_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS file_tag (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_id TEXT NOT NULL,
    tag_name TEXT NOT NULL,
    tag_color TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tag_id),
    UNIQUE (tag_name)
);

CREATE TABLE IF NOT EXISTS file_tag_rel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rel_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (rel_id),
    UNIQUE (file_id, tag_id),
    FOREIGN KEY (file_id) REFERENCES file_info(file_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES file_tag(tag_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    task_type TEXT NOT NULL CHECK (task_type IN ('summary', 'qa', 'rewrite', 'translate', 'continue', 'polish', 'replace')),
    file_id TEXT NOT NULL,
    selected_range TEXT,
    read_scope TEXT NOT NULL,
    model_provider TEXT,
    model_name TEXT,
    prompt_text TEXT,
    task_status TEXT NOT NULL DEFAULT 'pending' CHECK (task_status IN ('pending', 'running', 'success', 'failed', 'cancelled')),
    error_message TEXT,
    created_by TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    UNIQUE (task_id),
    FOREIGN KEY (file_id) REFERENCES file_info(file_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES user_account(user_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS ai_message (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    message_content TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (message_id),
    FOREIGN KEY (task_id) REFERENCES ai_task(task_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS backup_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_id TEXT NOT NULL,
    backup_name TEXT NOT NULL,
    backup_type TEXT NOT NULL DEFAULT 'manual' CHECK (backup_type IN ('manual', 'scheduled')),
    encrypted INTEGER NOT NULL DEFAULT 1 CHECK (encrypted IN (0, 1)),
    backup_status TEXT NOT NULL DEFAULT 'pending' CHECK (backup_status IN ('pending', 'running', 'success', 'failed', 'cancelled')),
    git_repo_url TEXT,
    git_branch TEXT,
    git_commit_id TEXT,
    archive_path TEXT,
    manifest_path TEXT,
    started_at DATETIME,
    finished_at DATETIME,
    created_by TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (backup_id),
    FOREIGN KEY (created_by) REFERENCES user_account(user_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS backup_manifest (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manifest_id TEXT NOT NULL,
    backup_id TEXT NOT NULL,
    manifest_version TEXT NOT NULL,
    object_count INTEGER NOT NULL DEFAULT 0 CHECK (object_count >= 0),
    metadata_checksum TEXT,
    manifest_checksum TEXT,
    restore_status TEXT NOT NULL DEFAULT 'not_restored' CHECK (restore_status IN ('not_restored', 'restoring', 'restored', 'failed')),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (manifest_id),
    FOREIGN KEY (backup_id) REFERENCES backup_record(backup_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id TEXT NOT NULL,
    user_id TEXT,
    action_type TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    action_result TEXT NOT NULL DEFAULT 'success' CHECK (action_result IN ('success', 'failed')),
    detail TEXT,
    client_ip TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (log_id),
    FOREIGN KEY (user_id) REFERENCES user_account(user_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS system_setting (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_key TEXT NOT NULL,
    setting_value TEXT,
    value_type TEXT NOT NULL DEFAULT 'string' CHECK (value_type IN ('string', 'boolean', 'number', 'json')),
    group_name TEXT NOT NULL,
    description TEXT,
    is_public INTEGER NOT NULL DEFAULT 0 CHECK (is_public IN (0, 1)),
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT,
    UNIQUE (setting_key),
    FOREIGN KEY (updated_by) REFERENCES user_account(user_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS file_key (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_id TEXT NOT NULL,
    key_material TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active_completed' CHECK (status IN ('expired', 'active_rotating', 'active_completed')),
    is_active INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1)),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    activated_at DATETIME,
    completed_at DATETIME,
    expired_at DATETIME,
    UNIQUE (key_id)
);

CREATE INDEX IF NOT EXISTS idx_user_session_user_id ON user_session(user_id);
CREATE INDEX IF NOT EXISTS idx_user_session_expires_at ON user_session(expires_at);

CREATE INDEX IF NOT EXISTS idx_file_path_parent_path_id ON file_path(parent_path_id);
CREATE INDEX IF NOT EXISTS idx_file_path_hidden_status ON file_path(is_hidden, status);
CREATE INDEX IF NOT EXISTS idx_file_path_type_status ON file_path(path_type, status);
CREATE INDEX IF NOT EXISTS idx_file_path_storage_path ON file_path(storage_path);

CREATE INDEX IF NOT EXISTS idx_file_info_path_id ON file_info(path_id);
CREATE INDEX IF NOT EXISTS idx_file_info_type_status ON file_info(file_type, status);
CREATE INDEX IF NOT EXISTS idx_file_info_hidden_status ON file_info(is_hidden, status);
CREATE INDEX IF NOT EXISTS idx_file_info_visibility_status ON file_info(visibility_type, status);
CREATE INDEX IF NOT EXISTS idx_file_info_created_at ON file_info(created_at);
CREATE INDEX IF NOT EXISTS idx_file_info_updated_at ON file_info(updated_at);
CREATE INDEX IF NOT EXISTS idx_file_info_last_accessed_at ON file_info(last_accessed_at);
CREATE INDEX IF NOT EXISTS idx_file_info_checksum_sha256 ON file_info(checksum_sha256);
CREATE INDEX IF NOT EXISTS idx_file_info_encryption_key_status ON file_info(encryption_enabled, key_id, status);

CREATE INDEX IF NOT EXISTS idx_file_tag_status ON file_tag(status);
CREATE INDEX IF NOT EXISTS idx_file_tag_rel_file_id ON file_tag_rel(file_id);
CREATE INDEX IF NOT EXISTS idx_file_tag_rel_tag_id ON file_tag_rel(tag_id);

CREATE INDEX IF NOT EXISTS idx_ai_task_file_id ON ai_task(file_id);
CREATE INDEX IF NOT EXISTS idx_ai_task_status_created_at ON ai_task(task_status, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_message_task_id_created_at ON ai_message(task_id, created_at);

CREATE INDEX IF NOT EXISTS idx_backup_record_status_created_at ON backup_record(backup_status, created_at);
CREATE INDEX IF NOT EXISTS idx_backup_manifest_backup_id ON backup_manifest(backup_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_user_id_created_at ON audit_log(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_target ON audit_log(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action_type_created_at ON audit_log(action_type, created_at);

CREATE INDEX IF NOT EXISTS idx_system_setting_group_name ON system_setting(group_name);
CREATE INDEX IF NOT EXISTS idx_system_setting_public_group ON system_setting(is_public, group_name);
CREATE UNIQUE INDEX IF NOT EXISTS uq_file_key_one_active ON file_key(is_active) WHERE is_active = 1;
CREATE INDEX IF NOT EXISTS idx_file_key_active ON file_key(is_active, status);

INSERT OR IGNORE INTO system_setting (
    setting_key,
    setting_value,
    value_type,
    group_name,
    description,
    is_public
) VALUES
    ('storage.encryption_enabled', 'true', 'boolean', 'storage', '是否默认启用文件本体加密', 1),
    ('hidden.feature_enabled', 'true', 'boolean', 'hidden', '是否启用文件隐藏功能', 1),
    ('hidden.show_hidden_default', 'false', 'boolean', 'hidden', '默认是否展示隐藏内容', 0),
    ('backup.git_enabled', 'true', 'boolean', 'backup', '是否启用 Git 备份能力', 1),
    ('backup.encrypt_before_push', 'true', 'boolean', 'backup', '备份推送到第三方前是否加密', 1),
    ('ai.feature_enabled', 'true', 'boolean', 'ai', '是否启用文件内 AI 能力', 1),
    ('ai.providers', '[]', 'json', 'ai', 'AI 模型提供方配置列表', 0),
    ('ai.active_provider_id', NULL, 'string', 'ai', '当前默认使用的 AI 模型配置', 1),
    ('ai.allow_summary_writeback', 'true', 'boolean', 'ai', '是否允许 AI 摘要回写文件元数据', 1);

COMMIT;
