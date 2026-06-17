# AI Story

面向长篇小说创作的 Agent-first IDE。在统一工作区里管理章节、素材与记忆，由 Agent 辅助写作，所有正文改动经用户确认后才会落库。

## 功能概览

- 本地账号注册与登录
- 小说与工作区：章节树、文件夹、回收站、导入导出
- TipTap 章节编辑器，支持选中文本交给 Agent
- Agent 对话：多轮会话、上下文组装、流式输出
- 人类确认机制：Agent 改写需审批后才写入正文
- 分层记忆：关键记忆、素材库、角色状态、人物关系、时间线
- 全小说搜索：跨章节检索正文与标题，一键定位
- 向量检索：Milvus + Ollama 本地 embedding（可配置外部模型）

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 19、Vite、Ant Design、TipTap |
| 后端 | FastAPI、SQLAlchemy、Alembic、LangGraph |
| 数据 | PostgreSQL、Milvus |
| 本地模型 | Ollama |
| 部署 | Docker Compose |
| 桌面 | Tauri（macOS / Linux / Windows，依赖 Docker） |

## 环境要求

- Docker Desktop（macOS）或 Docker Engine + Compose V2（Linux）
- 建议可用内存 ≥ 8 GB（Milvus、Ollama 会占用一定资源）
- 首次构建需能拉取镜像；国内网络建议保留默认 npm 镜像配置

## 快速开始

### 一键安装（推荐）

```bash
git clone <repo-url>
cd ai-story
chmod +x install.sh
./install.sh
```

脚本会自动：

1. 检测并安装 Docker（macOS 通过 Homebrew，Linux 通过官方脚本）
2. 从 `.env.example` 生成 `.env`，并配置 npm 源
3. 构建镜像并启动全部服务

仅安装环境、暂不启动服务：

```bash
./install.sh --no-start
```

海外网络可指定 npm 官方源：

```bash
NPM_REGISTRY=https://registry.npmjs.org ./install.sh
```

### 手动启动

```bash
cp .env.example .env
docker compose --env-file .env up -d --build
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |
| Postgres | `localhost:5433` |
| Ollama | http://localhost:11434 |

首次使用请在页面**注册账号**，系统不会预置测试用户。

如需本地演示账号，可在服务启动后执行：

```bash
./scripts/db-seed.sh
```

默认会创建 `demo@example.com` / `demo` / `secret123`。账号已存在时会跳过。

## 桌面应用（macOS / Linux / Windows）

若希望以桌面应用方式使用（带环境检测与 Docker 自动安装），见 [`desktop/README.md`](desktop/README.md)。

```bash
cd desktop
npm install
npm run tauri:dev      # 开发
npm run tauri:build    # 构建安装包
```

桌面版仍会启动 Docker Compose 栈；首次运行会自动检测并尝试安装 Docker Desktop。支持系统托盘、可选退出时停止容器，Windows 安装包由 GitHub Actions 构建。

## 命令行工具

仓库包含 Go 编写的 `ai-story` CLI，用于从终端调用后端 HTTP 接口和 Agent runtime 工具。CLI 默认连接 `http://localhost:8000`，也可以通过 `--base-url` 或 `AI_STORY_API_BASE` 指定后端地址。

```bash
cd cli
go build ./cmd/ai-story
./ai-story --help
./ai-story auth login --login demo@example.com --password secret123
./ai-story api request GET /health
./ai-story tools list
./ai-story tools run <novel-id> calculate --arg 'expression=(12 + 8) * 15%'
```

常用开发命令：

```bash
make cli-test
make cli-build
```

## 数据库初始化

后端容器启动时会自动执行 `alembic upgrade head`（见 `backend/docker-entrypoint.sh`）。

如需在宿主机手动初始化（**不依赖本地 Python 虚拟环境**）：

```bash
./scripts/db-migrate.sh
```

或：

```bash
make db-migrate
```

等价命令：

```bash
docker compose --env-file .env up -d postgres
docker compose --env-file .env run --rm api alembic upgrade head
```

查看当前迁移版本：

```bash
docker compose --env-file .env run --rm api alembic current
```

## 常用命令

```bash
# 查看服务状态
docker compose --env-file .env ps

# 查看日志
docker compose --env-file .env logs -f api
docker compose --env-file .env logs -f web

# 重启后端
docker compose --env-file .env up -d --build api

# 重启前端
docker compose --env-file .env up -d --build web

# 停止并移除容器（保留数据卷）
docker compose --env-file .env down

# 停止并清除数据（慎用）
docker compose --env-file .env down -v
```

Makefile 快捷方式：

```bash
make up          # 前台启动
make down        # 停止
make db-migrate  # 数据库迁移
make cli-test    # 运行 CLI 测试
make cli-build   # 构建 CLI
make test        # 运行前后端测试
```

## 本地开发

适合需要热重载、断点调试的场景。基础设施仍建议用 Docker 跑，应用可在宿主机运行。

### 1. 启动依赖服务

```bash
docker compose --env-file .env up -d postgres milvus ollama
./scripts/db-migrate.sh
```

### 2. 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

export DATABASE_URL=postgresql+asyncpg://ai_story:ai_story@localhost:5433/ai_story
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 3. 前端

```bash
cd frontend
npm ci
npm run dev
```

开发服务器默认 http://localhost:5173 ，通过 `VITE_API_BASE` 连接后端。

### 4. 运行测试

```bash
# 后端
cd backend && source .venv/bin/activate && pytest -v

# 前端
cd frontend && npm test

# CLI
cd cli && go test ./...
```

## 配置说明

复制 `.env.example` 为 `.env` 后，可按需修改：

| 变量 | 说明 |
|------|------|
| `JWT_SECRET` | 登录令牌密钥，生产环境务必修改 |
| `API_PORT` / `WEB_PORT` | 后端、前端宿主机端口 |
| `POSTGRES_HOST_PORT` | Postgres 对外端口（默认 5433） |
| `OLLAMA_EMBEDDING_MODEL` | 本地 embedding 模型 |
| `NPM_REGISTRY` | 前端 Docker 构建用的 npm 源 |
| `VITE_API_BASE` | 前端访问后端的地址 |

Agent 使用的对话 / 写作 / 向量模型在应用内「Agent 配置」页面设置，需自行准备 API Key 或本地 Ollama。

## 项目结构

```text
ai-story/
├── backend/          # FastAPI 后端
│   ├── app/          # 业务代码、Agent、API 路由
│   └── alembic/      # 数据库迁移
├── frontend/         # React 前端
├── cli/              # Go 命令行客户端
├── desktop/          # Tauri 桌面壳（Docker 环境检测与启动）
├── docker-compose.yml
├── install.sh        # 一键安装脚本
├── scripts/
│   └── db-migrate.sh # 数据库迁移脚本
└── .env.example      # 环境变量模板
```

## 常见问题

### 前端 Docker 构建时 `npm ci` 网络失败

国内网络常见。确认 `.env` 中有：

```env
NPM_REGISTRY=https://registry.npmmirror.com
```

然后重新构建：

```bash
docker compose --env-file .env up -d --build web
```

### 后端启动失败，提示找不到迁移版本

通常是镜像过旧。强制重建后端：

```bash
docker compose --env-file .env build --no-cache api
docker compose --env-file .env up -d api
```

或先手动迁移再启动：

```bash
./scripts/db-migrate.sh
docker compose --env-file .env up -d api
```

### Docker 已安装但脚本提示未就绪

macOS 请先打开 **Docker Desktop**，待菜单栏图标显示运行中后再执行 `./install.sh`。

### 登录报 Invalid credentials

数据库迁移只创建表结构，**不会自动创建用户**。登录页以前预填的 `demo` 账号并不存在。

处理方式（二选一）：

1. 在前端切换到 **注册** 标签，新建账号后登录
2. 服务启动后执行 `./scripts/db-seed.sh` 创建演示账号

```bash
./scripts/db-seed.sh
# 默认账号: demo@example.com / demo / secret123
```

### 没有预置账号或示例小说

属于预期行为。请在前端点击 **注册** 创建账号，或执行：

```bash
./scripts/db-seed.sh
```

创建演示账号后再登录。Agent 能力需在「Agent 配置」中绑定模型。

## 许可证

见仓库许可证文件（如有）。
