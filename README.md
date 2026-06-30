# DigitalCard

> 面向企业的数字名片与客户经营平台，让名片成为品牌展示、客户连接和业务增长的数字入口。

![Version](https://img.shields.io/badge/version-0.3.0-26734d.svg)
![Python](https://img.shields.io/badge/Python-3.12+-3776ab.svg)
![Node](https://img.shields.io/badge/Node.js-22+-339933.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)
![Vue](https://img.shields.io/badge/Vue-3.5+-42b883.svg)
![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)

## 当前版本

V0.3.0 已完成企业空间、租户隔离与角色权限能力，当前仓库包含：

- FastAPI 后端服务、统一错误响应、请求日志和请求 ID；
- 应用存活检查、数据库就绪检查和自动 OpenAPI 文档；
- SQLAlchemy 数据库基础设施和 Alembic 迁移基线；
- Vue 3 + TypeScript 管理端；
- Vue 3 + TypeScript 移动 H5 工程；
- 后端接口测试、前端组件测试和代码检查；
- 本地一键启动脚本、Docker Compose 和 GitHub Actions CI。
- 邮箱密码登录、会话刷新、安全退出和当前账户查询；
- Argon2 密码哈希、密码强度校验、失败锁定和登录审计；
- 管理员创建、启停和重置账户密码；
- 短期访问令牌、HttpOnly 刷新 Cookie、令牌轮换与即时撤销；
- 管理端登录页、鉴权路由、强制改密、账户管理和无权限页面。
- 平台企业空间创建、暂停、恢复与生命周期管理；
- 企业资料、Logo、简介和联系方式维护；
- 部门树创建、编辑、排序、移动和安全停用；
- 企业管理员、内容管理员、销售和普通员工四类企业角色；
- 企业角色与权限点绑定、后端实时权限检查；
- 基于 `company_id` 的服务端租户隔离和企业变更审计；
- 企业、部门、角色权限和审计管理页面。

当前版本不包含完整员工档案和数字名片业务。认证设计见 [账户与认证说明](docs/AUTHENTICATION.md)，租户模型见 [租户隔离与权限说明](docs/TENANCY_AND_PERMISSIONS.md)，后续范围见 [版本迭代需求文档](docs/ITERATION_REQUIREMENTS.md)。

## 快速开始

### 环境要求

| 工具 | 最低版本 | 用途 |
| --- | --- | --- |
| Python | 3.12 | 后端运行环境 |
| uv 或 pip | uv 最新稳定版 / pip 24+ | Python 依赖和虚拟环境管理，二选一 |
| Node.js | 22.12 | 前端运行环境 |
| npm | 10 | 前端依赖和工作区管理 |
| Docker | 可选 | 容器化启动 |

### Windows 一键启动

在项目根目录执行：

```powershell
.\scripts\dev.ps1
```

脚本首次运行会自动完成以下操作：

1. 根据 `.env.example` 创建本地 `.env`；
2. 安装 Python 与前端依赖；
3. 执行数据库迁移；
4. 同时启动 API、管理端和 H5。

首次安装需要能够访问 Python 与 npm 软件源。启动完成后访问：

| 服务 | 地址 |
| --- | --- |
| 管理端 | <http://localhost:5173> |
| H5 | <http://localhost:5174> |
| API | <http://localhost:8000> |
| API 文档 | <http://localhost:8000/docs> |
| OpenAPI | <http://localhost:8000/openapi.json> |
| 存活检查 | <http://localhost:8000/api/v1/health> |
| 数据库就绪检查 | <http://localhost:8000/api/v1/ready> |

按 `Ctrl+C` 可同时停止三个开发服务。

### 创建首个管理员

完成安装和数据库迁移后，执行以下命令并按提示输入密码：

```powershell
.\scripts\create-admin.ps1 --email admin@example.com --name "系统管理员"
```

密码输入不会显示在终端，也不会进入命令历史。该账户是平台管理员；登录后先在“企业管理”创建企业，再在“账户管理”创建对应的企业管理员。

### 分步启动

需要分别调试服务时，可以按以下方式启动。

```powershell
# 1. 创建环境配置
Copy-Item .env.example .env

# 2. 安装依赖并迁移数据库
uv sync
npm install
uv run alembic -c backend/alembic.ini upgrade head

# 3. 启动后端
uv run uvicorn digitalcard.main:app --app-dir backend/src --reload --port 8000

# 4. 在另外两个终端分别启动前端
npm run dev -w @digitalcard/admin
npm run dev -w @digitalcard/h5
```

也可以先执行初始化脚本，再按需启动服务：

```powershell
.\scripts\setup.ps1
```

### 使用 pip 安装

不使用 uv 时，可以通过标准 `venv + pip` 安装相同的运行、开发和测试依赖：

```powershell
# 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 仅安装后端运行依赖
python -m pip install -r requirements.txt

# 开发环境请改用这一条，它会同时安装测试和代码检查工具
python -m pip install -r requirements-dev.txt
```

也可以执行 pip 初始化脚本，它会创建环境配置和虚拟环境，同时安装前后端依赖并执行迁移：

```powershell
.\scripts\setup-pip.ps1
```

初始化后分别启动各服务：

```powershell
# 后端
.\.venv\Scripts\python.exe -m uvicorn digitalcard.main:app --app-dir backend/src --reload --port 8000

# 管理端与 H5（分别在新终端运行）
npm run dev -w @digitalcard/admin
npm run dev -w @digitalcard/h5
```

`requirements.txt` 对应生产运行依赖，`requirements-dev.txt` 在其基础上增加测试、覆盖率和代码检查工具。修改 Python 依赖时必须同步更新这两个文件与 `pyproject.toml`。

## 配置规范

应用通过环境变量读取配置。根目录 `.env.example` 是本地模板，不得提交实际 `.env`。

| 变量 | 必填 | 默认值 / 示例 | 说明 |
| --- | --- | --- | --- |
| `APP_NAME` | 否 | `DigitalCard API` | 服务名称 |
| `APP_ENV` | 否 | `development` | `development`、`test`、`staging` 或 `production` |
| `SECRET_KEY` | 是 | 无安全默认值 | 至少 32 个字符；生产环境必须使用随机密钥 |
| `DATABASE_URL` | 否 | `sqlite:///./data/digitalcard.db` | SQLAlchemy 数据库连接地址 |
| `LOG_LEVEL` | 否 | `INFO` | 日志级别 |
| `CORS_ORIGINS` | 否 | 本地两个前端地址 | 逗号分隔的可信来源 |
| `VITE_API_BASE_URL` | 否 | 本地 API 地址 | 前端构建时的 API 基础地址 |
| `ACCESS_TOKEN_MINUTES` | 否 | `15` | 访问令牌有效分钟数，范围 5～60 |
| `REFRESH_TOKEN_DAYS` | 否 | `7` | 刷新会话有效天数，范围 1～30 |
| `LOGIN_MAX_ATTEMPTS` | 否 | `5` | 连续失败锁定阈值 |
| `LOGIN_LOCK_MINUTES` | 否 | `15` | 账户临时锁定分钟数 |

不同环境的参考模板位于 `deploy/env/`。应用在 `SECRET_KEY` 缺失、过短或生产环境仍使用示例密钥时会拒绝启动并给出配置错误。

> 不要将密码、密钥、令牌、生产数据库地址或客户数据提交到版本库。

## 数据库迁移

```powershell
# 升级到最新版本
uv run alembic -c backend/alembic.ini upgrade head

# 查看当前版本
uv run alembic -c backend/alembic.ini current

# 创建新迁移
uv run alembic -c backend/alembic.ini revision --autogenerate -m "describe change"

# 回退一个版本
uv run alembic -c backend/alembic.ini downgrade -1
```

使用 pip 虚拟环境时，将上述命令中的 `uv run alembic` 替换为 `python -m alembic`。

业务模型新增后，需要在 `backend/migrations/env.py` 中确保模型已被加载，随后审查自动生成的迁移内容，不能未经检查直接执行。

## 质量检查

运行完整检查：

```powershell
.\scripts\check.ps1
```

也可以单独执行：

```powershell
uv run ruff check backend
uv run ruff format --check backend
uv run pytest
npm run typecheck
npm test
npm run build
```

使用 pip 虚拟环境时，后端检查命令对应为：

```powershell
python -m ruff check backend
python -m ruff format --check backend
python -m pytest
```

CI 会在推送到 `main` 或创建 Pull Request 时执行相同的后端检查、迁移验证、前端测试和生产构建。

## Docker 启动

先创建环境文件，再启动容器：

```powershell
Copy-Item .env.example .env
docker compose up --build
```

容器地址：

- 管理端：<http://localhost:8080>
- H5：<http://localhost:8081>
- API 与文档：<http://localhost:8000>、<http://localhost:8000/docs>

停止服务：

```powershell
docker compose down
```

本地 SQLite 数据保存在命名卷中。生产部署前需要替换示例密钥、配置正式数据库和可信域名，并根据实际基础设施补充备份、TLS、监控与资源限制。

## 项目结构

```text
DigitalCard/
├── backend/
│   ├── migrations/              # Alembic 迁移
│   ├── src/digitalcard/
│   │   ├── api/                 # API 路由
│   │   ├── core/                # 配置、日志与错误处理
│   │   ├── db/                  # 数据库基础设施
│   │   ├── middleware/          # HTTP 中间件
│   │   ├── models/              # SQLAlchemy 业务模型
│   │   ├── schemas/             # API 请求与响应模型
│   │   ├── services/            # 密码与令牌服务
│   │   └── main.py              # FastAPI 入口
│   ├── tests/                   # 后端测试
│   ├── alembic.ini
│   └── Dockerfile
├── frontend/
│   ├── admin/                   # 企业管理端
│   ├── h5/                      # 移动端名片页面
│   └── Dockerfile
├── deploy/
│   ├── env/                     # 分环境配置模板
│   └── nginx/                   # 前端容器配置
├── docs/                        # 产品与研发文档
├── scripts/                     # 初始化、启动和检查脚本
├── .github/workflows/ci.yml     # 持续集成
├── .env.example
├── compose.yaml
├── package.json                 # npm 工作区
├── pyproject.toml               # uv / Python 项目配置
├── requirements.txt             # pip 运行依赖
└── requirements-dev.txt         # pip 开发与测试依赖
```

## API 响应约定

错误响应采用统一结构，并通过响应头 `X-Request-ID` 提供可追踪的请求编号：

```json
{
  "error": {
    "code": "not_found",
    "message": "Not Found",
    "request_id": "5e61e637899d45d6a3b6d9cb5f70edb2"
  }
}
```

后续业务接口统一挂载在 `/api/v1` 下。公开 API 发生不兼容变化时应增加版本，不得静默破坏已有客户端。

## 版本路线

- [x] **V0.1.0：工程底座** — 后端、管理端、H5、迁移、测试、CI 与容器
- [x] **V0.2.0：账户与登录** — 账户管理、登录状态与基础安全
- [x] **V0.3.0：企业与权限** — 企业空间、组织架构、租户隔离与 RBAC
- [ ] **V0.4.0～V1.0.0：数字名片 MVP** — 员工、名片、分享、产品、线索与 CRM
- [ ] **V1.1.0～V1.5.0：经营平台** — 分析、营销、SaaS、AI 与开放平台

完整范围、依赖关系和验收条件见 [版本迭代需求文档](docs/ITERATION_REQUIREMENTS.md)。

## 开源许可

本项目采用 [Apache License 2.0](LICENSE) 许可证。
