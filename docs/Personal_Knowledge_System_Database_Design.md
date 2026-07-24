# Personal Knowledge System 数据库表结构设计文档

## 1. 文档说明

### 1.1 目的
本文档用于定义 `Personal Knowledge System` 的数据库结构设计，重点包括：

- 当前阶段需要哪些核心表
- 每张表承担什么业务职责
- 这些表之间如何交互
- 每张表的字段级结构建议

### 1.2 当前设计约束

- 当前以单用户模式为主
- 文件本体不直接进数据库
- 文件业务元数据集中在单一 `file_info` 表中
- 路径隐藏和文件隐藏不单独拆表，直接放在主业务表字段中
- “是否开启文件隐藏功能”等系统级规则统一放在 `system_setting`
- 所有表统一增加业务前缀，方便在数据库中快速区分语义

---

## 2. 表命名规范

### 2.1 命名规则

统一采用：

`业务前缀_业务对象`

例如：

- 用户管理：`user_xxx`
- 文件管理：`file_xxx`
- AI 管理：`ai_xxx`
- 备份管理：`backup_xxx`
- 审计管理：`audit_xxx`
- 系统配置：`system_xxx`

说明：

- 路径管理与文件管理同属于“文件管理模块”，统一使用 `file_` 前缀
- 也就是说，目录树、路径节点、文件信息、文件标签、文件标签关系，都放在 `file_` 语义下命名

### 2.2 当前建议使用的业务前缀

| 前缀 | 语义 |
| --- | --- |
| `user_` | 用户与登录会话 |
| `file_` | 文件管理模块，覆盖目录树、路径、文件及标签 |
| `ai_` | AI 任务与消息 |
| `backup_` | 备份与恢复 |
| `audit_` | 审计日志 |
| `system_` | 系统配置 |

---

## 3. 核心表总览

当前建议的核心表如下：

| 表名 | 用途 | 当前是否必需 |
| --- | --- | --- |
| `user_account` | 用户账户信息 | 必需 |
| `user_session` | 登录会话信息 | 建议 |
| `file_path` | 树状目录与路径结构 | 必需 |
| `file_info` | 文件主表，保存文件全部核心业务元数据 | 必需 |
| `file_tag` | 标签定义 | 必需 |
| `file_tag_rel` | 文件与标签关系表 | 必需 |
| `ai_task` | AI 调用任务记录 | 建议 |
| `ai_message` | AI 对话消息记录 | 可选 |
| `backup_record` | 备份记录 | 必需 |
| `backup_manifest` | 备份清单索引记录 | 建议 |
| `audit_log` | 审计日志 | 必需 |
| `system_setting` | 系统配置 | 必需 |

---

## 4. 每张表的业务职责

### 4.1 `user_account`

职责：

- 保存登录用户信息
- 当前阶段主要保存单管理员账号

### 4.2 `user_session`

职责：

- 保存登录会话
- 支持 Token 刷新、会话失效、主动登出

### 4.3 `file_path`

职责：

- 保存目录树结构
- 支持普通路径、私密路径
- 支持父子级关系
- 保存路径隐藏状态

### 4.4 `file_info`

职责：

- 这是文件业务主表
- 保存文件全部核心业务元数据
- 保存文件摘要、文件加密状态、存储对象映射信息
- 保存文件隐藏状态

说明：

- 你当前要求“不拆分业务对象表和摘要表”，因此文件对象映射、摘要信息、加密信息都集中放在这一张表

### 4.5 `file_tag`

职责：

- 保存标签定义

### 4.6 `file_tag_rel`

职责：

- 保存文件与标签的多对多关系

### 4.7 `ai_task`

职责：

- 保存 AI 调用任务
- 用于记录模型调用、上下文范围、执行状态

### 4.8 `ai_message`

职责：

- 保存 AI 面板中的消息历史
- 当前不是绝对必需，但如果保留对话历史就值得建

### 4.9 `backup_record`

职责：

- 保存备份任务执行记录

### 4.10 `backup_manifest`

职责：

- 保存备份包 manifest 索引信息
- 用于恢复前快速定位备份清单

### 4.11 `audit_log`

职责：

- 保存关键审计操作

### 4.12 `system_setting`

职责：

- 保存系统全局配置
- 保存隐藏功能开关、AI 配置、备份配置等系统级设置

---

## 5. 表之间的交互逻辑

### 5.1 登录逻辑

涉及表：

- `user_account`
- `user_session`
- `audit_log`

交互逻辑：

1. 用户输入账号密码
2. 系统查询 `user_account`
3. 校验密码哈希
4. 创建或刷新 `user_session`
5. 写入 `audit_log`

### 5.2 路径树逻辑

涉及表：

- `file_path`
- `system_setting`
- `audit_log`

交互逻辑：

1. 前端加载目录树
2. 系统查询 `system_setting` 判断是否开启显示隐藏内容
3. 系统查询 `file_path`
4. 若未开启显示隐藏内容，则基于 `file_path.is_hidden` 过滤隐藏路径
5. 返回树状结构
6. 对目录的新增、重命名、移动、隐藏操作写入 `audit_log`

### 5.3 文件上传逻辑

涉及表：

- `file_info`
- `audit_log`

交互逻辑：

1. 用户上传文件
2. 系统生成 `file_id`
3. 文件流式加密后写入磁盘或对象存储
4. 将原始文件名、随机存储对象名、文件大小、加密状态、摘要等写入 `file_info`
5. 写入 `audit_log`

### 5.4 文件列表逻辑

涉及表：

- `file_path`
- `file_info`
- `file_tag`
- `file_tag_rel`
- `system_setting`

交互逻辑：

1. 用户点击目录
2. 系统查询该目录下 `file_info`
3. 联表标签关系
4. 查询 `system_setting` 判断是否开启显示隐藏内容
5. 若未开启显示隐藏内容，则基于 `file_info.is_hidden` 过滤隐藏文件
6. 返回列表

### 5.5 文件打开逻辑

涉及表：

- `file_info`
- `system_setting`
- `audit_log`

交互逻辑：

1. 用户双击或打开文件
2. 系统查询 `system_setting` 判断是否允许访问隐藏文件
3. 查询 `file_info` 获取文件元数据、存储对象名、加密状态
4. 若当前文件为隐藏文件，则校验当前会话是否允许查看
5. 读取文件本体并流式解密
6. 返回给前端预览或下载
7. 写入 `audit_log`

### 5.6 隐藏路径 / 隐藏文件逻辑

涉及表：

- `file_path`
- `file_info`
- `system_setting`
- `audit_log`

交互逻辑：

1. 用户对目录或文件执行隐藏
2. 目录隐藏状态直接写入 `file_path.is_hidden`
3. 文件隐藏状态直接写入 `file_info.is_hidden`
4. “是否开启文件隐藏功能”“是否允许显示隐藏内容”这类系统级开关写入 `system_setting`
5. 查询列表和树时应用这些字段和系统配置
6. 写入 `audit_log`

### 5.7 标签与搜索逻辑

涉及表：

- `file_info`
- `file_tag`
- `file_tag_rel`

交互逻辑：

1. 用户输入关键词或按标签筛选
2. 系统查询 `file_info`
3. 联表 `file_tag_rel`、`file_tag`
4. 若搜索摘要，则直接搜索 `file_info.summary_content`
5. 返回结果

### 5.8 AI 调用逻辑

涉及表：

- `file_info`
- `ai_task`
- `ai_message`
- `audit_log`

交互逻辑：

1. 用户打开某个文件或选中某段内容
2. 系统确认 AI 可读取范围
3. 创建 `ai_task`
4. 若保留对话历史，则写入 `ai_message`
5. AI 返回结果
6. 若用户保存摘要，则回写 `file_info.summary_content`
7. 写入 `audit_log`

### 5.9 备份逻辑

涉及表：

- `file_path`
- `file_info`
- `file_tag`
- `file_tag_rel`
- `backup_record`
- `backup_manifest`
- `audit_log`
- `system_setting`

交互逻辑：

1. 用户触发备份
2. 系统创建 `backup_record`
3. 导出目录、文件、标签、隐藏状态字段、配置
4. 生成 manifest
5. 在 `backup_manifest` 记录清单索引
6. 更新 `backup_record` 状态
7. 写入 `audit_log`

### 5.10 恢复逻辑

涉及表：

- `backup_record`
- `backup_manifest`
- `file_path`
- `file_info`
- `file_tag`
- `file_tag_rel`
- `audit_log`
- `system_setting`

交互逻辑：

1. 用户选择恢复版本
2. 系统读取 `backup_manifest`
3. 重建目录树
4. 重建文件元数据
5. 重建标签关系
6. 重建路径与文件的隐藏状态字段
7. 恢复系统配置
8. 更新恢复状态
9. 写入 `audit_log`

---

## 6. 当前建议的最小表集

如果你希望先快速启动开发，第一阶段建议至少落以下 8 张表：

1. `user_account`
2. `file_path`
3. `file_info`
4. `file_tag`
5. `file_tag_rel`
6. `backup_record`
7. `audit_log`
8. `system_setting`

如果希望同时支持登录会话、AI 历史与恢复索引，再补：

9. `user_session`
10. `ai_task`
11. `ai_message`
12. `backup_manifest`

---

## 7. 字段级表结构设计

以下字段设计采用你要求的格式：

`字段名 | 类型 | 含义`

---

## 8. `user_account`

| 字段名 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `INTEGER` / `BIGINT` | 自增主键 |
| `user_id` | `VARCHAR(64)` | 用户稳定唯一标识 |
| `username` | `VARCHAR(128)` | 登录用户名 |
| `password_hash` | `VARCHAR(255)` | 密码哈希值 |
| `display_name` | `VARCHAR(128)` | 页面展示昵称 |
| `status` | `VARCHAR(32)` | 账号状态，如 `active` / `disabled` |
| `last_login_at` | `DATETIME` | 最后登录时间 |
| `created_at` | `DATETIME` | 创建时间 |
| `updated_at` | `DATETIME` | 更新时间 |

---

## 9. `user_session`

| 字段名 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `INTEGER` / `BIGINT` | 自增主键 |
| `session_id` | `VARCHAR(64)` | 会话唯一标识 |
| `user_id` | `VARCHAR(64)` | 关联用户标识 |
| `access_token` | `TEXT` | 当前访问令牌或其摘要 |
| `refresh_token` | `TEXT` | 刷新令牌或其摘要 |
| `client_ip` | `VARCHAR(64)` | 登录来源 IP |
| `user_agent` | `TEXT` | 客户端标识 |
| `expires_at` | `DATETIME` | 会话过期时间 |
| `last_active_at` | `DATETIME` | 最后活跃时间 |
| `created_at` | `DATETIME` | 创建时间 |

---

## 10. `file_path`

| 字段名 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `INTEGER` / `BIGINT` | 自增主键 |
| `path_id` | `VARCHAR(64)` | 路径稳定唯一标识 |
| `parent_path_id` | `VARCHAR(64)` | 父路径标识，根节点可为空 |
| `path_name` | `VARCHAR(255)` | 路径名称 |
| `path_type` | `VARCHAR(32)` | 路径类型，如 `normal` / `private` |
| `path_level` | `INTEGER` | 路径层级 |
| `sort_index` | `INTEGER` | 排序值 |
| `full_path` | `TEXT` | 冗余保存完整路径字符串 |
| `description` | `TEXT` | 路径说明 |
| `is_hidden` | `BOOLEAN` | 当前路径是否隐藏 |
| `status` | `VARCHAR(32)` | 状态，如 `active` / `deleted` |
| `created_at` | `DATETIME` | 创建时间 |
| `updated_at` | `DATETIME` | 更新时间 |

---

## 11. `file_info`

| 字段名 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `INTEGER` / `BIGINT` | 自增主键 |
| `file_id` | `VARCHAR(64)` | 文件稳定唯一标识 |
| `path_id` | `VARCHAR(64)` | 所属路径标识 |
| `original_name` | `VARCHAR(512)` | 原始文件名 |
| `storage_object_name` | `VARCHAR(512)` | 存储层随机对象名 |
| `storage_path` | `TEXT` | 存储层实际路径或对象 Key |
| `storage_provider` | `VARCHAR(64)` | 存储提供方，如 `local` / `minio` |
| `mime_type` | `VARCHAR(255)` | MIME 类型 |
| `file_ext` | `VARCHAR(32)` | 文件扩展名 |
| `file_type` | `VARCHAR(32)` | 业务文件类型，如 `text` / `image` / `video` / `pdf` / `audio` / `other` |
| `size_bytes` | `BIGINT` | 文件大小，单位字节 |
| `checksum_sha256` | `VARCHAR(128)` | 文件内容校验值 |
| `encryption_enabled` | `BOOLEAN` | 是否启用文件本体加密 |
| `key_wrap_version` | `VARCHAR(64)` | 文件密钥封装版本 |
| `summary_content` | `TEXT` | 文件摘要内容 |
| `summary_source` | `VARCHAR(32)` | 摘要来源，如 `manual` / `ai` |
| `summary_updated_at` | `DATETIME` | 摘要更新时间 |
| `is_hidden` | `BOOLEAN` | 当前文件是否隐藏 |
| `visibility_type` | `VARCHAR(32)` | 可见性类型，如 `normal` / `private` |
| `status` | `VARCHAR(32)` | 文件状态，如 `active` / `deleted` / `archived` |
| `created_by` | `VARCHAR(64)` | 创建人用户标识 |
| `updated_by` | `VARCHAR(64)` | 更新人用户标识 |
| `created_at` | `DATETIME` | 创建时间 |
| `updated_at` | `DATETIME` | 更新时间 |
| `last_accessed_at` | `DATETIME` | 最近访问时间 |

---

## 12. `file_tag`

| 字段名 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `INTEGER` / `BIGINT` | 自增主键 |
| `tag_id` | `VARCHAR(64)` | 标签稳定唯一标识 |
| `tag_name` | `VARCHAR(128)` | 标签名称 |
| `tag_color` | `VARCHAR(32)` | 标签颜色 |
| `status` | `VARCHAR(32)` | 标签状态 |
| `created_at` | `DATETIME` | 创建时间 |
| `updated_at` | `DATETIME` | 更新时间 |

---

## 13. `file_tag_rel`

| 字段名 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `INTEGER` / `BIGINT` | 自增主键 |
| `rel_id` | `VARCHAR(64)` | 关系唯一标识 |
| `file_id` | `VARCHAR(64)` | 关联文件标识 |
| `tag_id` | `VARCHAR(64)` | 关联标签标识 |
| `created_at` | `DATETIME` | 创建时间 |

---

## 14. `ai_task`

| 字段名 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `INTEGER` / `BIGINT` | 自增主键 |
| `task_id` | `VARCHAR(64)` | AI 任务唯一标识 |
| `task_type` | `VARCHAR(64)` | 任务类型，如 `summary` / `qa` / `rewrite` / `translate` |
| `file_id` | `VARCHAR(64)` | 关联文件标识 |
| `selected_range` | `TEXT` | 当前选中段落范围描述 |
| `read_scope` | `TEXT` | 本次 AI 可读取范围说明 |
| `model_provider` | `VARCHAR(64)` | 模型提供方 |
| `model_name` | `VARCHAR(128)` | 模型名称 |
| `prompt_text` | `TEXT` | 用户输入或系统生成提示词摘要 |
| `task_status` | `VARCHAR(32)` | 任务状态，如 `pending` / `success` / `failed` |
| `error_message` | `TEXT` | 失败原因 |
| `created_by` | `VARCHAR(64)` | 发起人 |
| `created_at` | `DATETIME` | 创建时间 |
| `completed_at` | `DATETIME` | 完成时间 |

---

## 15. `ai_message`

| 字段名 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `INTEGER` / `BIGINT` | 自增主键 |
| `message_id` | `VARCHAR(64)` | 消息唯一标识 |
| `task_id` | `VARCHAR(64)` | 关联 AI 任务标识 |
| `role` | `VARCHAR(32)` | 消息角色，如 `user` / `assistant` / `system` |
| `message_content` | `TEXT` | 消息内容 |
| `created_at` | `DATETIME` | 创建时间 |

---

## 16. `backup_record`

| 字段名 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `INTEGER` / `BIGINT` | 自增主键 |
| `backup_id` | `VARCHAR(64)` | 备份任务唯一标识 |
| `backup_name` | `VARCHAR(255)` | 备份名称 |
| `backup_type` | `VARCHAR(32)` | 备份类型，如 `manual` / `scheduled` |
| `encrypted` | `BOOLEAN` | 是否启用备份级加密 |
| `backup_status` | `VARCHAR(32)` | 备份状态 |
| `git_repo_url` | `TEXT` | Git 仓库地址 |
| `git_branch` | `VARCHAR(128)` | Git 分支 |
| `git_commit_id` | `VARCHAR(128)` | Git 提交 ID |
| `archive_path` | `TEXT` | 备份包路径 |
| `manifest_path` | `TEXT` | manifest 文件路径 |
| `started_at` | `DATETIME` | 开始时间 |
| `finished_at` | `DATETIME` | 结束时间 |
| `created_by` | `VARCHAR(64)` | 发起人 |
| `created_at` | `DATETIME` | 创建时间 |

---

## 17. `backup_manifest`

| 字段名 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `INTEGER` / `BIGINT` | 自增主键 |
| `manifest_id` | `VARCHAR(64)` | manifest 唯一标识 |
| `backup_id` | `VARCHAR(64)` | 关联备份标识 |
| `manifest_version` | `VARCHAR(32)` | manifest 版本 |
| `object_count` | `INTEGER` | 包含对象数量 |
| `metadata_checksum` | `VARCHAR(128)` | 元数据校验值 |
| `manifest_checksum` | `VARCHAR(128)` | manifest 校验值 |
| `restore_status` | `VARCHAR(32)` | 恢复状态 |
| `created_at` | `DATETIME` | 创建时间 |

---

## 18. `audit_log`

| 字段名 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `INTEGER` / `BIGINT` | 自增主键 |
| `log_id` | `VARCHAR(64)` | 日志唯一标识 |
| `user_id` | `VARCHAR(64)` | 操作用户标识 |
| `action_type` | `VARCHAR(64)` | 操作类型，如 `login` / `upload` / `open_file` / `backup` |
| `target_type` | `VARCHAR(64)` | 目标类型，如 `file` / `path` / `backup` / `ai_task` |
| `target_id` | `VARCHAR(64)` | 目标对象标识 |
| `action_result` | `VARCHAR(32)` | 操作结果，如 `success` / `failed` |
| `detail` | `TEXT` | 操作详情 |
| `client_ip` | `VARCHAR(64)` | 来源 IP |
| `created_at` | `DATETIME` | 创建时间 |

---

## 19. `system_setting`

| 字段名 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `INTEGER` / `BIGINT` | 自增主键 |
| `setting_key` | `VARCHAR(128)` | 配置键 |
| `setting_value` | `TEXT` | 配置值 |
| `value_type` | `VARCHAR(32)` | 值类型，如 `string` / `boolean` / `json` |
| `group_name` | `VARCHAR(64)` | 配置分组，如 `storage` / `ai` / `backup` / `hidden` |
| `description` | `TEXT` | 配置说明 |
| `is_public` | `BOOLEAN` | 是否可在普通设置页展示 |
| `updated_at` | `DATETIME` | 更新时间 |
| `updated_by` | `VARCHAR(64)` | 更新人 |

---

## 20. 数据库访问与 SQL 规范

这一部分用于约束后续项目开发中的数据库访问方式，重点目标有两个：

- 降低手写拼接 SQL 带来的 SQL 注入风险
- 保证多人协作时查询风格、事务处理、字段使用方式一致

### 20.1 总体原则

- 后端统一使用 `SQLAlchemy 2.x` 作为数据库访问层
- 优先使用 ORM 或参数化查询，不允许直接拼接用户输入到 SQL 字符串中
- 允许手写 SQL，但必须使用参数绑定
- 查询、写入、事务控制统一收敛到 Repository / DAO 层，不允许在路由层直接散写 SQL
- 所有数据库变更统一通过迁移工具管理，不允许线上手改表结构

### 20.2 推荐技术选型

- ORM / 查询层：`SQLAlchemy 2.x`
- 数据迁移：`Alembic`
- 本地开发数据库：`SQLite`
- 后续扩展数据库：`PostgreSQL`

说明：

- 当前阶段使用 `SQLite` 是为了轻量部署和快速开发
- 如果后续文件量、并发量、备份任务量明显上升，可以平滑迁移到 `PostgreSQL`
- 即使当前使用 `SQLite`，代码层也尽量按照 `SQLAlchemy` 的参数化和事务规范来写，避免后续迁移成本

### 20.3 禁止事项

以下写法默认禁止：

- 使用 `f-string` 拼接 SQL
- 使用 `%` 或 `format()` 将用户输入拼接到 SQL 中
- 在路由层直接写原生 SQL
- 将排序字段、表名、列名直接由前端字符串透传
- 在没有事务控制的情况下执行多步写操作

错误示例：

```python
sql = f"SELECT * FROM file_info WHERE original_name = '{keyword}'"
```

### 20.4 推荐写法

推荐优先使用 ORM 表达式：

```python
stmt = select(FileInfo).where(FileInfo.original_name == keyword)
result = session.execute(stmt)
```

如果必须写原生 SQL，也必须使用参数绑定：

```python
from sqlalchemy import text

stmt = text("SELECT * FROM file_info WHERE original_name = :keyword")
result = session.execute(stmt, {"keyword": keyword})
```

### 20.5 排序、筛选、分页规范

- 普通筛选条件必须走参数绑定
- 排序字段不能直接使用前端传入值，必须通过白名单映射
- 分页统一使用 `limit + offset`
- 文件列表默认按 `updated_at DESC, id DESC` 排序
- 审计日志默认按 `created_at DESC, id DESC` 排序
- 路径树默认按 `sort_index ASC, id ASC` 排序

排序字段白名单示例：

```python
SORT_FIELD_MAP = {
    "name": FileInfo.original_name,
    "size": FileInfo.size_bytes,
    "createdAt": FileInfo.created_at,
    "updatedAt": FileInfo.updated_at,
}
```

### 20.6 模糊搜索规范

- 文件搜索范围当前仅限文件元数据、标签、人工/AI 摘要
- 不直接搜索加密后的文件本体内容
- 模糊搜索统一对 `original_name`、`summary_content`、标签名称等字段做条件组合
- 搜索语句必须先应用“隐藏过滤”和“状态过滤”，再应用关键词条件

建议顺序：

1. 过滤 `status = active`
2. 根据系统配置过滤隐藏项
3. 根据 `path_id` 或标签筛选
4. 最后叠加关键词模糊搜索

### 20.7 事务规范

- 单次文件上传涉及“写元数据 + 写审计日志”时，数据库写入部分必须放进同一事务
- 标签绑定、文件移动、文件隐藏等多步操作必须使用事务
- 备份记录与备份清单写入必须使用事务
- AI 摘要写回 `file_info.summary_content` 时，应与 `ai_task` 状态更新放在同一事务中

说明：

- 文件本体写入磁盘或对象存储不一定和数据库事务天然一致
- 因此需要在业务层补充失败回滚、补偿删除、状态修正机制

### 20.8 软删除与状态规范

- 当前表设计优先使用 `status` 字段表示业务状态
- 不建议物理删除文件、目录、标签、备份记录
- 文件删除建议先改为 `deleted`
- 路径删除建议先改为 `deleted`
- 审计日志原则上不允许删除

### 20.9 字段使用规范

- 所有业务主标识统一使用显式业务 ID，例如 `file_id`、`path_id`、`task_id`
- 自增 `id` 只作为数据库内部主键，不作为对外暴露 ID
- 时间字段统一使用 `DATETIME`
- 布尔字段在 `SQLite` 中按 `0 / 1` 存储，在代码层映射为布尔值
- 枚举值尽量收敛在有限集合中，并在表结构或代码层做约束

### 20.10 索引规范

- 唯一业务标识字段必须建唯一索引
- 高频筛选字段要建普通索引，例如 `path_id`、`status`、`is_hidden`
- 高频排序字段可结合查询场景建组合索引
- 不要在低区分度且几乎不用作筛选的字段上滥建索引
- 每新增一个复杂列表接口，都应回看其查询条件并评估是否需要补索引

### 20.11 Repository 分层建议

建议按业务模块拆分 Repository：

- `user_repository`
- `file_path_repository`
- `file_info_repository`
- `file_tag_repository`
- `ai_task_repository`
- `backup_repository`
- `audit_repository`
- `system_setting_repository`

约束建议：

- Repository 负责数据库读写
- Service 负责业务编排、事务边界、异常处理
- API / Router 只负责参数接收、权限校验、响应输出

### 20.12 与当前项目的直接约束结论

结合当前项目，数据库访问层建议直接执行以下规则：

1. 所有文件列表、目录树、搜索接口统一使用 `SQLAlchemy`
2. 不允许在业务代码中手写字符串拼接 SQL
3. 如必须写原生 SQL，必须使用 `text()` + 命名参数
4. 排序字段必须使用白名单映射
5. 所有多表写操作必须显式事务控制
6. 表结构变更统一走迁移脚本，不直接修改线上数据库

---

## 21. 当前建议结论

按你现在的要求，文件模型已经收敛为“一个主文件表承载所有文件业务元数据”的方案：

- 不再拆 `file_objects`
- 不再拆 `file_summaries`
- 文件摘要、存储对象名、加密状态、校验值等都放进 `file_info`
- 不再单独拆路径隐藏规则表和文件隐藏规则表
- 路径隐藏状态放进 `file_path.is_hidden`
- 文件隐藏状态放进 `file_info.is_hidden`
- “是否开启文件隐藏功能”等系统级开关放进 `system_setting`

如果你认可这版结构，下一步最适合继续补的是：

1. 主键、唯一约束、索引设计
2. 外键关系建议
3. SQLite 建表 SQL 初稿
