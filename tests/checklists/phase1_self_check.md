# PFMT 第一阶段自检清单

## 环境与配置

- [ ] 使用 `pwsh ./scripts/dev/bootstrap_dev.ps1 -CreateLocalEnvFile` 创建 `pfmt-py312`。
- [ ] `conda run -n pfmt-py312 python --version` 输出 Python 3.12。
- [ ] `.env` 由 `.env.example` 本地复制得到，且示例密钥已经替换成本机开发值。
- [ ] `PFMT_STORAGE_ROOT` 指向的存储根目录及其 `db`、`data`、`tmp`、`preview`、`backup`、`logs`、`objects` 子目录均存在。
- [ ] `.env`、SQLite 数据库、日志、密文对象和缓存没有被 Git 跟踪。

## 后端

- [ ] `pwsh ./scripts/dev/start_server.ps1` 可启动 FastAPI。
- [ ] 未登录访问 `/api/settings`、`/api/paths/tree`、`/api/files/upload` 会被拒绝。
- [ ] 登录成功返回 bearer token，会话过期或退出后不能继续访问业务接口。
- [ ] 配置接口可读写并持久化：加密开关、隐藏功能开关、默认展示隐藏、本地存储根路径。
- [ ] 上传接口使用流式读取和流式加密写入，失败时能回滚元数据或清理已写文件。
- [ ] 上传后的存储对象名随机化，不等于原始文件名，也不包含原始扩展名之外的敏感信息。
- [ ] Markdown 查看接口只支持已授权文件，并对渲染 HTML 做安全处理。

## 前端

- [ ] `pwsh ./scripts/dev/start_web.ps1` 可启动 Vue 3 + Vite。
- [ ] 未登录用户只能看到登录页，登录后进入主布局。
- [ ] 主布局包含顶部导航、左侧目录树、右侧内容区域和配置入口。
- [ ] 配置页可展示并保存第一阶段基础开关。
- [ ] 上传入口能选择 `.md` 文件并展示上传结果。
- [ ] 目录树刷新后能看到上传文件所在路径。
- [ ] Markdown 查看面板能打开已上传 `.md` 文件。

## 联调主流程

- [ ] 调用 `pwsh ./scripts/dev/run_tests.ps1`，静态合同校验和已有单元测试通过。
- [ ] 同时启动后端与前端后，调用 `pwsh ./scripts/dev/self_check.ps1 -RunApi`。
- [ ] 完成登录、配置读取、配置更新、目录树读取、Markdown 上传加密、Markdown 查看。
- [ ] 浏览器手工验证登录到 Markdown 查看这条链路无阻断。
