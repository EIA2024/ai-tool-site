# Developer Documentation

## Architecture

```
┌──────────────────────┐     REST / WS / SSE      ┌──────────────────────┐
│   Frontend           │◄────────────────────────►│   Backend            │
│   React + Vite + TS  │                          │   Python + FastAPI   │
│   Port 5173          │                          │   Port 8000          │
│                      │                          │                      │
│   API base:          │                          │                      │
│   Dev: Vite proxy    │                          │                      │
│   Docker: direct     │                          │                      │
│   VITE_API_BASE      │                          │                      │
└──────────────────────┘                          └──────┬───────────────┘
                                                         │
                                           ┌─────────────┴─────────────┐
                                           │  PostgreSQL    Redis       │
                                           │  Port 5432     Port 6379  │
                                           └───────────────────────────┘
```

## Prerequisites

- Node.js >= 22
- Python >= 3.11
- Docker & Docker Compose (for containerized mode)
- PostgreSQL 16 (for non-Docker mode)
- Redis 7 (for non-Docker mode)

## Quick Start — Docker (Recommended)

```bash
# Clone both repos (or use the workspace root for development)
# From project root:
docker compose up --build
```

This starts four services:
- `frontend` at http://localhost:5173
- `backend` at http://localhost:8000
- `postgres` at localhost:5432
- `redis` at localhost:6379

## Non-Docker Development

### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies (includes dev extras: pytest, ruff, aiosqlite, …)
pip install -r requirements-dev.txt

# Recommended: run with a file-based SQLite database — no PostgreSQL/Redis needed.
# Creates tables idempotently and starts uvicorn with auto-reload.
python run_dev.py
```

To run against the full stack (PostgreSQL + Redis) instead:

```bash
# Ensure PostgreSQL and Redis are running (or `docker compose up postgres redis`)
# Configure backend/.env (or root .env) with DATABASE_URL / REDIS_URL

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api`, `/ws`, and `/sse` to the backend at `localhost:8000`.

> **Docker 模式**下，前端由 `serve` 静态服务器托管（无 proxy）。需在构建时通过 `VITE_API_BASE` 指定后端地址：
> ```yaml
> # docker-compose.yml
> frontend:
>   build:
>     args:
>       VITE_API_BASE: http://localhost:8000/api
> ```
> `lib/api.ts` 中 `BASE = import.meta.env.VITE_API_BASE || "/api"`，Dev 模式默认使用 Vite proxy。

### Database

Ensure PostgreSQL and Redis are running locally or via Docker:

```bash
# Start only infra services
docker compose up postgres redis
```

## Verification Checklist

- [ ] **AC-1**: Open http://localhost:5173 → tool list loads → click "Blank Tool" → enter text → submit → see echo response
- [ ] **AC-2**: Open http://localhost:5173 → click "Chat Tool" → click "New Chat" → send message → receive echo reply
- [ ] **AC-3**: Open http://localhost:5173 → "Code Agent Flow Visualizer" appears → click → 9 stages navigable → save a record → persists after refresh
- [ ] **AC-4**: Create a new file `backend/app/tools/modules/my_tool.py` extending `BaseTool` → register in `registry.py` → tool appears in the list
- [ ] **AC-5**: Send chat messages → restart backend → reconnect → messages are persisted (check via API)
- [ ] **AC-6**: `docker compose up --build` starts all four services successfully and backend runs `alembic upgrade head`
- [ ] **AC-7**: In non-Docker mode, Vite proxy handles both REST (`/api/tools`) and WebSocket (`/ws/chat`)

## Project Structure

```
root/
├── frontend/                  # React + Vite + TypeScript SPA
│   ├── src/
│   │   ├── pages/tools/       # Tool page implementations
│   │   ├── components/        # Reusable UI components
│   │   ├── lib/               # API and WebSocket clients
│   │   ├── hooks/             # React hooks
│   │   └── types/             # TypeScript type definitions
│   ├── Dockerfile
│   └── package.json
│
├── backend/                   # Python + FastAPI backend
│   ├── app/
│   │   ├── api/               # REST API routes
│   │   ├── ws/                # WebSocket handlers
│   │   ├── sse/               # SSE event streams
│   │   ├── tools/             # Tool registry + modules
│   │   ├── models/            # SQLAlchemy ORM models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic (chat history, cache)
│   │   └── db/                # Database session management
│   ├── alembic/               # Database migrations
│   ├── Dockerfile
│   └── pyproject.toml
│
├── docker-compose.yml         # Full-stack orchestration
├── .env.example               # Environment variables template
└── docs/development.md        # This file
```

## Adding a New Tool

1. Create `backend/app/tools/modules/my_tool.py`:

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.base import BaseTool
from app.core.errors import ToolError


class MyTool(BaseTool):
    tool_id = "my_tool"
    name = "My Tool"
    description = "Description of my tool"
    mode = "request-response"  # or "realtime"

    async def handle_invoke(self, payload: dict, db: AsyncSession) -> dict:
        # Your logic here. Return the success data payload only; the API
        # layer wraps it in the {"success": true, "data": ...} envelope.
        if not payload.get("input"):
            raise ToolError("input is required", code="INVALID_INPUT")
        return {"result": payload["input"]}
```

2. Register in `backend/app/tools/registry.py`:

```python
from app.tools.modules.my_tool import MyTool
tool_registry.register(MyTool())
```

3. (Optional) Add a frontend page at `frontend/src/pages/tools/MyToolPage.tsx` and update `App.tsx` routes.
4. (Optional, database-backed tools) Add a new model in `backend/app/models/__init__.py`, create an Alembic migration:

```bash
cd backend
alembic revision -m "add my_tool_records"
# Write migration by hand (see 002_add_agent_practice_records.py as example)
alembic upgrade head
```

> **注意**：如果工具需要数据库持久化，`handle_invoke` 接收注入的 `db: AsyncSession`，可直接执行查询；不要在此层 commit —— 由路由层统一 commit/rollback。预期的业务失败应抛出 `ToolError`（或 `ValidationError`/`NotFoundError`）等类型化异常，由路由层转换为统一 JSON 信封；不要 catch 后返回裸结构。参考 `code_agent_flow_viz.py` 的 action dispatch 模式。
>
> **Docker 模式**：后端容器启动时自动运行 `alembic upgrade head`。前端容器通过构建参数 `VITE_API_BASE=http://localhost:8000/api` 直接请求后端。Dev 模式下通过 Vite proxy 转发。（非 Docker 开发模式无需额外配置。）

### 真实案例参考

[Code Agent Flow Visualizer](backend/app/tools/modules/code_agent_flow_viz.py) 是一个完整的数据库持久化工具案例，包含：

- **后端**：`AgentPracticeRecord` 模型 → Alembic 迁移 → CRUD 服务 → 工具模块（action dispatch，db 注入 + 类型化错误）
- **前端**：TypeScript 类型扩展 → 全功能页面（表单/历史/导出/导入）→ 路由注册
- **约束**：`tool_id = "code_agent_flow_viz"`，`mode = "request-response"`，所有 CRUD 通过单一 invoke 端点
