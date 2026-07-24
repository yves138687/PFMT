# PFMT 第一阶段 API 合同

本合同用于第一阶段前后端联调和 `scripts/dev/self_check.ps1 -RunApi` 自检。接口命名优先保持 REST 风格，业务代码落地时如需调整路径，应同步更新本文件和 `phase1_api_contract.json`。

## 通用约定

- 基础地址：`PFMT_API_BASE_URL + PFMT_API_PREFIX`，本地默认 `http://127.0.0.1:8000/api`
- 兼容前缀：当前后端保留 `/api/v1` 兼容入口；第一阶段本地联调以 `.env.example` 中的 `/api` 为准
- 鉴权方式：登录成功后使用 `Authorization: Bearer <access_token>`
- 响应格式：建议统一返回 JSON；错误响应至少包含 `error_code` 或 `code`，以及 `message`
- 文件存储：上传后的 `storage_object_name` 必须为随机化对象名，不得等于原始文件名
- 加密策略：当 `storage.encryption_enabled=true` 时，文件本体写入必须走流式加密，不允许整文件一次性读入内存

## 合同清单

| 场景 | 方法 | 路径 | 目的 | 核心断言 |
| --- | --- | --- | --- | --- |
| 登录 | `POST` | `/api/auth/login` | 单用户登录并取得访问令牌 | 返回 `access_token`，未登录不能访问业务接口 |
| 退出 | `POST` | `/api/auth/logout` | 主动结束当前会话 | 当前令牌失效或服务端记录退出 |
| 配置读取 | `GET` | `/api/settings` | 读取第一阶段基础开关 | 返回 `storage.encryption_enabled`、`hidden.feature_enabled`、`hidden.show_hidden_default`、`storage.local_root` |
| 配置更新 | `PUT` | `/api/settings/{setting_key}` | 修改并持久化单个配置项 | 二次读取时配置值保持一致 |
| 目录树 | `GET` | `/api/paths/tree` | 获取根节点和基础目录树 | 返回根节点，节点包含 `path_id`、`path_name`、`children` |
| 创建目录 | `POST` | `/api/paths` | 创建基础目录节点 | 返回目录 `path_id`，可在目录树中看到 |
| 上传加密 | `POST` | `/api/files/upload` | 上传文件并写入元数据及密文对象 | 返回 `file_id`、`original_name`、随机 `storage_object_name`、`encryption_enabled=true` |
| Markdown 查看 | `GET` | `/api/files/{file_id}/markdown` | 查看已上传 `.md` 文件 | 返回解密后的 Markdown 文本内容 |

## 自检主流程

1. 调用 `/api/auth/login` 登录，保存令牌。
2. 调用 `/api/settings` 读取配置，确认第一阶段开关存在。
3. 分别调用 `/api/settings/storage.encryption_enabled`、`/api/settings/hidden.feature_enabled`、`/api/settings/hidden.show_hidden_default` 更新配置。
4. 调用 `/api/paths/tree`，确认根节点存在。
5. 使用 `tests/fixtures/markdown/phase1_markdown_sample.md` 调用 `/api/files/upload`，确认返回随机化对象名且启用加密。
6. 调用 `/api/files/{file_id}/markdown`，确认 Markdown 内容可读取。

## 安全与隐私断言

- `.env.example` 只能放示例值，不放真实密钥。
- API 响应不返回 `PFMT_FILE_MASTER_KEY`、派生文件密钥或明文存储路径。
- 存储对象名不可由原始文件名直接推导。
- 上传失败时不能留下孤立元数据；元数据写入失败时应清理已写入的文件对象。
- 隐藏内容展示必须受系统配置控制，并保留后续审计扩展点。
