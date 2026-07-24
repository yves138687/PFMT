# PFMT 测试说明

`tests/` 放跨前后端的合同、联调清单、样例文件和轻量环境约束测试。后端自身单元测试优先放 `server/tests/`，前端单元与组件测试优先放 `web/tests/`。

## 推荐执行顺序

```powershell
pwsh ./scripts/dev/bootstrap_dev.ps1 -CreateLocalEnvFile
pwsh ./scripts/dev/run_tests.ps1
pwsh ./scripts/dev/start_server.ps1
pwsh ./scripts/dev/start_web.ps1
pwsh ./scripts/dev/self_check.ps1 -RunApi
```

## 测试矩阵

| 层级 | 位置 | 工具 | 第一阶段覆盖 |
| --- | --- | --- | --- |
| 环境约束 | `tests/test_phase1_tooling.py` | `pytest` | conda 环境文件、脚本、`.env.example`、API 合同完整性 |
| 后端单元/集成 | `server/tests/` | `pytest` + `httpx` | 登录、配置、目录树、上传加密、Markdown 读取 |
| 前端单元/组件 | `web/tests/` | `Vitest` | 登录页、主布局、配置表单、上传入口、Markdown 查看面板 |
| 端到端 | `web/tests/e2e/` 或 `tests/e2e/` | `Playwright` | 浏览器内完成登录到 Markdown 查看主链路 |
| API 自检 | `scripts/dev/self_check.ps1 -RunApi` | PowerShell + REST | 按 `tests/contracts/phase1_api_contract.md` 做联调冒烟 |

## 合同同步规则

- 后端接口路径或字段变化时，同步更新 `tests/contracts/phase1_api_contract.md` 与 `tests/contracts/phase1_api_contract.json`。
- 前端联调应以合同字段为准，避免页面里散写临时接口。
- 第一阶段不引入 AI、全文检索、备份恢复的强制测试，只保留配置字段和后续扩展提醒。
