# Personal Knowledge System 项目结构约束文档

## 1. 文档目标

本文档用于约束 `Personal Knowledge System` 项目的目录结构、模块职责和文件放置规范，目标是：

- 让后续前后端开发都能快速理解目录职责
- 降低“文件乱放、脚本乱放、文档分散”的维护成本
- 保证 Python 后端、Vue 前端、文档、数据库脚本、运维脚本各自边界清晰

---

## 2. 总体目录原则

- 业务代码、文档、数据库脚本、运维脚本必须分目录管理
- 同一类职责只放在一个主目录下，避免重复落位
- `docs` 只放说明性文档，不放可执行脚本和 SQL
- `scripts` 只放脚本、初始化文件、数据库迁移和运维辅助内容
- 数据库建表 SQL 统一放在 `scripts/db`
- 前端与后端建议分为独立应用目录，避免后期边界混乱

---

## 3. 推荐项目顶层结构

推荐项目采用如下结构：

```text
PFMT/
├─ docs/
├─ scripts/
│  ├─ db/
│  ├─ dev/
│  ├─ build/
│  └─ deploy/
├─ server/
├─ web/
├─ storage/
├─ tests/
├─ .env.example
├─ .gitignore
└─ README.md
```

目录说明：

- `docs`：产品、技术、交互、数据库、迭代规划等文档
- `scripts/db`：建表 SQL、初始化 SQL、迁移辅助 SQL
- `scripts/dev`：本地开发脚本
- `scripts/build`：打包、构建、检查脚本
- `scripts/deploy`：部署、备份、恢复、发布脚本
- `server`：Python 后端工程
- `web`：Vue 前端工程
- `storage`：本地文件存储目录，仅开发环境可本地保留
- `tests`：跨模块集成测试，或顶层测试辅助资源

---

## 4. 文档目录约束

### 4.1 `docs/`

用途：

- 存放 PRD、技术架构、数据库设计、前端交互说明、迭代计划等文档

允许放入：

- Markdown 文档
- 架构图说明
- 接口设计说明
- 原型说明
- 评审记录

禁止放入：

- SQL 建表脚本
- 可执行脚本
- 临时测试文件
- 编译产物

建议命名方式：

- `Personal_Knowledge_System_PRD_Optimized.md`
- `Personal_Knowledge_System_Technical_Architecture.md`
- `Personal_Knowledge_System_Database_Design.md`
- `Personal_Knowledge_System_Project_Structure_Convention.md`

---

## 5. 脚本目录约束

### 5.1 `scripts/`

用途：

- 存放数据库脚本、开发辅助脚本、部署脚本、构建脚本

总原则：

- `scripts` 中的文件必须是“可执行、可复用、与工程运行相关”的内容
- 不承载产品说明，不与 `docs` 混放

### 5.2 `scripts/db/`

用途：

- 存放数据库初始化、建表、索引、迁移辅助 SQL

当前要求：

- 所有 SQL 文件统一放在该目录
- 当前主建表脚本应以该目录中的版本为准

建议内容：

- `001_init_schema.sql`
- `002_seed_system_setting.sql`
- `003_add_indexes.sql`
- `rollback_xxx.sql`

约束：

- SQL 文件使用递增编号或清晰版本号
- 一个 SQL 文件只处理一类变更
- 不允许把数据库脚本再复制一份到 `docs`

### 5.3 `scripts/dev/`

用途：

- 本地启动、测试、格式化、检查等开发脚本

建议内容：

- 启动后端
- 启动前端
- 初始化开发环境
- 导入测试数据

示例：

- `start_server.ps1`
- `start_web.ps1`
- `bootstrap_dev.ps1`

### 5.4 `scripts/build/`

用途：

- 构建产物、打包、静态检查相关脚本

建议内容：

- 前端打包
- 后端依赖冻结
- 代码质量检查

### 5.5 `scripts/deploy/`

用途：

- 部署、发布、备份、恢复相关脚本

建议内容：

- 服务部署
- 数据恢复
- 备份触发
- 环境检查

---

## 6. Python 后端目录约束

### 6.1 `server/`

用途：

- 存放后端全部 Python 业务代码

推荐结构：

```text
server/
├─ app/
│  ├─ api/
│  ├─ core/
│  ├─ models/
│  ├─ schemas/
│  ├─ repositories/
│  ├─ services/
│  ├─ utils/
│  └─ main.py
├─ migrations/
├─ tests/
├─ pyproject.toml
└─ README.md
```

### 6.2 `server/app/`

用途：

- 后端主应用目录

各子目录职责如下。

### 6.3 `server/app/api/`

用途：

- 定义接口路由层

职责：

- 接收请求参数
- 调用 Service
- 返回统一响应
- 做基础鉴权和参数校验

禁止事项：

- 不直接写复杂业务逻辑
- 不直接拼接 SQL
- 不直接操作文件加解密细节

### 6.4 `server/app/core/`

用途：

- 放置系统级基础能力

建议内容：

- 配置加载
- 数据库连接
- 安全组件
- 日志组件
- 加密配置
- AI 提供方配置

### 6.5 `server/app/models/`

用途：

- 放置 `SQLAlchemy` 模型

职责：

- 定义表结构映射
- 定义字段与约束
- 定义模型之间关系

约束：

- 只承载数据结构表达
- 不堆积复杂业务逻辑

### 6.6 `server/app/schemas/`

用途：

- 放置 `Pydantic` 请求和响应模型

职责：

- 定义接口入参
- 定义接口出参
- 做字段级校验

### 6.7 `server/app/repositories/`

用途：

- 数据访问层

职责：

- 统一封装数据库查询和写入
- 统一处理列表筛选、分页、排序白名单
- 对外暴露清晰的数据访问方法

约束：

- 原生 SQL 必须参数化
- 不允许手动拼接用户输入
- 不处理跨领域业务编排

### 6.8 `server/app/services/`

用途：

- 业务服务层

职责：

- 负责编排文件上传、文件隐藏、AI 摘要、备份恢复等业务流程
- 控制事务边界
- 处理领域异常

说明：

- 这里是后端核心业务逻辑的主要落点

### 6.9 `server/app/utils/`

用途：

- 放置通用工具函数

建议内容：

- 时间处理
- 哈希工具
- 路径工具
- 文件流工具
- 加密辅助工具

约束：

- `utils` 不承载核心业务规则
- 业务规则应留在 `services`

### 6.10 `server/migrations/`

用途：

- 存放数据库迁移文件

约束：

- 统一由 `Alembic` 管理
- 不手写散落式迁移文件到其他目录

### 6.11 `server/tests/`

用途：

- 后端单元测试与集成测试

建议分层：

- `unit/`
- `integration/`
- `fixtures/`

---

## 7. Vue 前端目录约束

### 7.1 `web/`

用途：

- 存放前端全部代码与构建配置

推荐结构：

```text
web/
├─ public/
├─ src/
│  ├─ api/
│  ├─ assets/
│  ├─ components/
│  ├─ composables/
│  ├─ layouts/
│  ├─ router/
│  ├─ stores/
│  ├─ styles/
│  ├─ types/
│  ├─ utils/
│  └─ views/
├─ tests/
├─ package.json
├─ vite.config.ts
└─ README.md
```

### 7.2 `web/public/`

用途：

- 放置不参与打包处理的静态资源

建议内容：

- favicon
- 固定静态文件

### 7.3 `web/src/api/`

用途：

- 统一封装前端接口请求

职责：

- 按业务模块拆接口文件
- 封装请求方法
- 统一处理鉴权头、错误码、请求超时

禁止事项：

- 页面内直接散写请求地址
- 重复写相同接口

### 7.4 `web/src/assets/`

用途：

- 放置图片、图标、字体、静态样式资源

### 7.5 `web/src/components/`

用途：

- 放置可复用组件

建议分类：

- 通用表格
- 文件卡片
- 文件列表
- 路径树
- AI 操作面板
- 统计卡片

### 7.6 `web/src/composables/`

用途：

- 存放 Vue 组合式逻辑

建议内容：

- 文件列表状态管理
- 路径树交互逻辑
- 文件预览状态
- AI 面板状态

### 7.7 `web/src/layouts/`

用途：

- 定义页面骨架布局

建议内容：

- 登录前布局
- 登录后主布局
- 文件阅读布局

### 7.8 `web/src/router/`

用途：

- 路由定义与路由守卫

职责：

- 页面路由注册
- 登录校验
- 路由元信息定义

### 7.9 `web/src/stores/`

用途：

- 全局状态管理

建议内容：

- 用户信息
- 系统设置
- 文件视图模式
- 当前打开文件上下文

### 7.10 `web/src/styles/`

用途：

- 放置全局样式、主题变量、布局基础样式

约束：

- 设计 Token 优先放这里
- 页面级零散样式尽量收敛，不要把主题变量散到组件里

### 7.11 `web/src/types/`

用途：

- 放置 TypeScript 类型定义

建议内容：

- 文件对象类型
- 目录对象类型
- 标签对象类型
- AI 任务类型

### 7.12 `web/src/utils/`

用途：

- 通用前端工具函数

建议内容：

- 文件大小格式化
- 时间格式化
- 路由辅助
- 下载辅助

### 7.13 `web/src/views/`

用途：

- 页面级视图

建议按业务拆分：

- `login/`
- `dashboard/`
- `file-browser/`
- `file-detail/`
- `settings/`

### 7.14 `web/tests/`

用途：

- 前端单元测试与组件测试

---

## 8. 文件存储目录约束

### 8.1 `storage/`

用途：

- 开发环境下本地文件本体存储目录

建议子目录：

- `storage/data/`：加密文件本体
- `storage/tmp/`：临时解密文件或临时处理文件
- `storage/preview/`：预览缓存
- `storage/backup/`：本地备份中间文件

约束：

- 默认不提交到 Git
- 生产环境可替换为对象存储或挂载盘
- 临时目录要有清理机制
- 解密后的临时文件必须设置过期清理

---

## 9. 测试目录约束

### 9.1 顶层 `tests/`

用途：

- 存放跨前后端、跨模块的集成验证用例或测试资源

建议内容：

- 测试样例文件
- API 联调脚本
- 端到端测试配置

说明：

- 如果测试主要服务于某个子工程，应优先放入 `server/tests` 或 `web/tests`
- 顶层 `tests` 更适合放公共测试资源和端到端测试

---

## 10. 配置文件约束

建议顶层保留：

- `.env.example`
- `.gitignore`
- `README.md`

说明：

- `.env.example` 用于说明需要哪些环境变量
- 不允许提交真实密钥、真实数据库密码、真实备份令牌
- 根目录 `README.md` 用于说明项目启动方式、目录结构和开发约定

---

## 11. 命名与分层约束

### 11.1 目录命名

- 统一使用小写英文
- 多单词目录使用中划线或单词直接组合，但同一层级要统一风格

### 11.2 文件命名

- Python 文件统一使用小写加下划线
- Vue 组件文件建议使用 `PascalCase`
- 文档文件建议使用明确语义英文名或既有文档命名规则
- SQL 文件建议使用版本号前缀

### 11.3 分层边界

- 前端不直接感知数据库结构
- Router 不直接操作 Repository
- Repository 不直接处理复杂业务编排
- `utils` 不替代 `services`
- 文档目录不承载脚本
- 脚本目录不承载产品设计说明

---

## 12. 当前阶段建议落地结构

结合当前项目阶段，建议优先先搭出最小结构：

```text
PFMT/
├─ docs/
├─ scripts/
│  └─ db/
├─ server/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ core/
│  │  ├─ models/
│  │  ├─ repositories/
│  │  ├─ schemas/
│  │  ├─ services/
│  │  └─ main.py
│  └─ tests/
├─ web/
│  ├─ src/
│  │  ├─ api/
│  │  ├─ components/
│  │  ├─ layouts/
│  │  ├─ router/
│  │  ├─ stores/
│  │  └─ views/
│  └─ tests/
└─ storage/
```

这一版已经足够支撑你当前的开发优先级：

- 单用户登录
- 文件树
- 文件上传
- 文件本体加密
- 文件展示与预览

---

## 13. 当前建议结论

当前项目目录规范建议收敛为以下原则：

1. `docs` 只放文档，不放 SQL 和脚本
2. `scripts/db` 统一管理所有数据库 SQL
3. 后端代码全部收口到 `server`
4. 前端代码全部收口到 `web`
5. 文件本体和缓存统一收口到 `storage`
6. 业务逻辑、数据访问、接口层必须分层
7. 目录结构优先为后续 AI、备份、加密能力扩展预留空间
