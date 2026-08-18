# AI Tool Site

一个集成多种 AI 开发工具的 Web 平台，提供从任务拆解到 Agent 工作流可视化的完整工具链。

## 工具

| 工具 | 模式 | 说明 |
|------|------|------|
| **Task Decomposer** | Request-Response | 将模糊的开发需求拆解为结构化 Agent 任务卡片，支持 DeepSeek 模型选择与历史记录管理 |
| **Code Agent Flow Visualizer** | Request-Response | 可视化 9 阶段编码 Agent 工作流，支持各阶段的实践记录保存、检索与管理 (PostgreSQL) |
| **Chat Tool** | Realtime (WebSocket) | 实时对话工具模板，基于 WebSocket 实现双向通信 |
| **Blank Tool** | Request-Response | 请求-响应模式的工具模板，用于快速集成新的 AI 工具 |

## 架构

```
project-root/
├── frontend/          # React + Vite + TypeScript 前端
│   └── src/
│       ├── components/     # 网站级 UI（Layout、NavBar、ErrorBoundary）
│       ├── pages/          # Dock、动态路由、Schema 渲染器、Usage
│       ├── lib/            # api / ToolClient / realtime 客户端
│       ├── types/          # Host–Plugin 契约类型（ToolManifest 等）
│       └── tool_plugins/   # 各工具专属前端 UI（chat、flow viz、task decomposer）
├── backend/           # Python FastAPI 后端
│   └── app/
│       ├── tool_host/      # Host runtime：契约、自动发现、REST/WS 网关、站点配置
│       ├── tool_plugins/   # 各插件：manifest + Pydantic handler + 模型/仓库
│       ├── api/            # 站点级 REST（config、audit）
│       ├── services/       # Host 级共享设施（llm、audit、cache）
│       ├── models/         # Host 级 ORM（audit）
│       ├── core/           # 配置、错误、限流、脱敏
│       └── db/             # 数据库会话管理
├── docker-compose.yml  # PostgreSQL + Redis + Backend + Frontend
└── docs/               # 开发文档
```

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 19, React Router, Vite, TypeScript |
| 后端 | Python 3.12, FastAPI, SQLAlchemy (async), Alembic |
| 数据库 | PostgreSQL 16, Redis 7 |
| AI | DeepSeek API |
| 基础设施 | Docker Compose |

## 快速开始

### 前提条件

- Docker & Docker Compose
- DeepSeek API Key（Task Decomposer 需要）

### 启动

```bash
# 1. 克隆并进入项目
git clone <repo-url>
cd ai-tool-site

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 3. 启动所有服务
docker compose up -d

# 4. 执行数据库迁移
docker compose exec backend alembic upgrade head

# 5. 访问 http://localhost:5173
```

### 本地开发（无 Docker）

**一键启动：**

```bash
# macOS
./start.sh

# macOS Finder：双击 start.command

# Windows（命令行运行或直接双击 start.bat）
start.bat
```

脚本会自动准备缺失的本地依赖，使用 SQLite 启动后端和 Vite 前端，并打开
`http://localhost:5173`。按 `Ctrl+C` 可同时停止前后端；不希望自动打开浏览器时使用
`./start.sh --no-open` 或 `./start.command --no-open`（macOS），或 `start.bat -NoOpen`
（Windows）。

**后端（推荐，使用 SQLite，无需 PostgreSQL/Redis）：**

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt

# 自动创建 SQLite 数据库并启动带热重载的 uvicorn
python run_dev.py
```

**后端（完整模式，需要 PostgreSQL 和 Redis）：**

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt

# 确保 PostgreSQL 和 Redis 已运行，配置 .env
uvicorn app.main:app --reload --port 8000
```

**前端：**

```bash
cd frontend
npm install
npm run dev
```

## 工具开发

新增一个工具只需一个**插件目录**：后端 `backend/app/tool_plugins/<tool_id>/`，复杂工具再可选加一个前端入口 `frontend/src/tool_plugins/<tool_id>/index.tsx`。网站（Host）会自动发现插件——**不需要**修改 `App.tsx`、导航或任何中心注册表；重新构建前端并重启后端后生效。

后端插件 = 一个 `plugin.py`，声明版本化 manifest 和具名 operation handler：

```python
# backend/app/tool_plugins/my_tool/plugin.py
from pydantic import BaseModel, Field

from app.tool_host.contracts import (
    OperationDefinition, ToolContext, ToolPlugin, ToolUi, Transport, UiKind,
)


class EchoInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class EchoOutput(BaseModel):
    echo: str


async def echo(payload: EchoInput, context: ToolContext) -> EchoOutput:
    return EchoOutput(echo=payload.text)


plugin = ToolPlugin(
    id="my_tool",
    version="1.0.0",
    name="My Tool",
    description="一个 request-response 示例工具",
    ui=ToolUi(kind=UiKind.SCHEMA),  # schema → 前端用通用表单渲染，无需写前端
    operations=(
        OperationDefinition(
            "echo", Transport.REQUEST_RESPONSE, EchoInput, EchoOutput, echo
        ),
    ),
)
```

- `ui.kind = "schema"`：前端用通用表单/结果渲染器自动承载，无需任何前端代码。
- `ui.kind = "custom"`：再放一个 `frontend/src/tool_plugins/my_tool/index.tsx`，默认导出组件，接收绑定好的 `ToolClient`，调用 `client.invoke(operation, payload)` 或 `client.connect(operation)`（realtime），不自行拼接 URL。
- `blank_tool` 是默认隐藏的 schema 示例插件。

持久化插件仍需显式编写 Alembic migration（插件发现不会自动改表）。关于返回数据 / 错误处理 / 数据库持久化的约定，详见 [AI 工具开发手册](docs/ai-tool-development-handbook.md)。

## 文档

- [开发文档](docs/development.md)
- [AI 工具开发手册](docs/ai-tool-development-handbook.md)
- [维护指南](docs/maintenance.md)
