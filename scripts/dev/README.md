# PFMT 本地开发脚本

本目录只放本地开发与自检脚本，不承载业务代码。脚本默认使用 PowerShell 7，并以 `conda run -n pfmt-py312` 调用后端工具，避免污染系统 Python 或其他 conda 环境。

## 首次准备

```powershell
pwsh ./scripts/dev/bootstrap_dev.ps1 -CreateLocalEnvFile
```

该命令会：

- 按 `scripts/dev/environment.yml` 创建 `pfmt-py312`
- 按 `.env` 中的 `PFMT_STORAGE_ROOT` 创建存储根目录、数据库目录、密文对象目录、临时目录、预览目录、备份目录和日志目录
- 可选从 `.env.example` 生成本机 `.env`

`.env` 只能保留在本地，不允许提交真实密钥。

## 本地启动

```powershell
scripts\dev\start_all.bat
pwsh ./scripts/dev/start_server.ps1
pwsh ./scripts/dev/start_web.ps1
```

`start_all.bat` 会分别打开后端和前端两个窗口，前端窗口会直接进入 `web` 目录，适合在 Windows 中双击一键启动。前端默认监听 `0.0.0.0`，窗口会打印本机和局域网访问地址；局域网设备访问 `http://本机IPv4:5173` 即可。前端依赖已存在时会跳过 `npm install` 并直接启动，避免 npm 反复处理已有依赖目录。当前仓库如果尚未生成 `server/app/main.py` 或 `web/package.json`，启动脚本会给出明确提示。主线程补齐 FastAPI 与 Vue 业务骨架后，这些脚本无需改名即可继续使用。

## 测试与自检

```powershell
pwsh ./scripts/dev/run_tests.ps1
pwsh ./scripts/dev/self_check.ps1
pwsh ./scripts/dev/self_check.ps1 -RunApi
```

默认自检只验证环境文件、合同和目录约束。`-RunApi` 会按 `tests/contracts/phase1_api_contract.md` 的第一阶段合同尝试调用登录、配置、目录树、上传加密和 Markdown 查看接口。
