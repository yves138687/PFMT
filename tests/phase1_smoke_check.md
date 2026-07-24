# 第一阶段自检清单

本清单用于前后端联调后快速确认主链路是否闭环。

- 后端：`GET /api/health` 返回 `{"status":"ok"}`
- 登录：默认开发账号 `admin / admin123456` 可登录，错误密码返回 `401`
- 鉴权：未带 Bearer Token 访问 `/api/paths/tree` 返回 `401`
- 配置：`/api/settings` 可读取并保存隐藏、加密、存储路径配置
- 目录树：根节点 `root` 存在，可创建子目录并在树中展示
- 上传：上传文件后数据库记录原始文件名，存储对象名为随机 `.pfmt`，不等于原文件名
- 加密：开启 `storage.encryption_enabled` 时，存储对象不包含明文内容
- Markdown：上传 `.md` 后可通过 `/api/files/{file_id}/markdown` 读取渲染内容
- 前端：登录页、主布局、左侧目录树、系统设置、上传页、Markdown 查看页可操作
