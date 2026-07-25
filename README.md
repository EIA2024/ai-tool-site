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
│       ├── components/     # 通用 UI 组件
│       ├── pages/          # 页面 & 工具页面
│       └── lib/            # API & WebSocket 客户端
├── backend/           # Python FastAPI 后端
│   └── app/
│       ├── api/            # REST 路由
│       ├── tools/          # 工具模块（可插拔架构）
│       ├── services/       # 业务逻辑层
│       ├── models/         # SQLAlchemy 模型
│       ├── schemas/        # Pydantic 校验
│       ├── ws/             # WebSocket 处理
│       ├── sse/            # Server-Sent Events
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

**后端：**

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

新工具只需继承 `BaseTool` 并注册到 `ToolRegistry`：

```python
from app.tools.base import BaseTool

class MyTool(BaseTool):
    tool_id = "my_tool"
    name = "My Tool"
    description = "My custom AI tool"
    mode = "request-response"

    async def handle_invoke(self, payload: dict) -> dict:
        # 你的工具逻辑
        return {"success": True, "data": {...}}

# 在 registry.py 中注册
tool_registry.register(MyTool())
```

前端对应添加页面并配置路由即可。

## 项目工作流

本项目的开发遵循一套 Prompt-native 的 AI 协作工作流（详见 `.agent-workspace/`），包括 Context 收集、Intent 确认、计划、执行、独立 Review 等阶段。

## 文档

- [开发文档](docs/development.md)
- [AI 工具开发手册](docs/ai-tool-development-handbook.md)
- [维护指南](docs/maintenance.md)
