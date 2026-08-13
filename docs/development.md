# Developer Documentation

## Architecture

```
┌──────────────────────┐     REST / WS           ┌──────────────────────┐
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

The Vite dev server proxies `/api` and `/ws` to the backend at `localhost:8000`.

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
- [ ] **AC-4**: Create `backend/app/tool_plugins/my_tool/plugin.py` (a `ToolPlugin` with one operation) → restart backend + rebuild frontend → tool appears in the Dock
- [ ] **AC-5**: Send chat messages → restart backend → reconnect → messages are persisted (check via API)
- [ ] **AC-6**: `docker compose up --build` starts all four services successfully and backend runs `alembic upgrade head`
- [ ] **AC-7**: In non-Docker mode, Vite proxy handles both REST (`/api/tools`) and WebSocket (`/ws/tools/...`)

## Project Structure

```
root/
├── frontend/                  # React + Vite + TypeScript SPA
│   ├── src/
│   │   ├── pages/             # Dock (ToolList), dynamic ToolPage, Usage, schema renderer
│   │   ├── components/        # Site-level UI (Layout, NavBar, ErrorBoundary)
│   │   ├── lib/               # api / ToolClient / realtime clients
│   │   ├── types/             # Host–Plugin contract types (ToolManifest, …)
│   │   └── tool_plugins/      # Per-tool custom UI (chat_tool, code_agent_flow_viz, task_decomposer)
│   ├── vitest.config.ts
│   ├── Dockerfile
│   └── package.json
│
├── backend/                   # Python + FastAPI backend
│   ├── app/
│   │   ├── tool_host/         # Host runtime: contracts, discovery, REST/WS gateway, site config
│   │   ├── tool_plugins/      # Plugins: manifest + Pydantic handlers + models/repositories
│   │   ├── api/               # Site-level REST (config, audit)
│   │   ├── services/          # Shared Host facilities (llm, audit, cache)
│   │   ├── models/            # Host ORM models (audit)
│   │   ├── core/              # Config, errors, rate limit, redaction
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

A new tool is a **plugin directory** — no edits to `App.tsx`, navigation, or any
central registry. The backend discovers plugins automatically; a frontend
rebuild + backend restart makes it live.

1. Create `backend/app/tool_plugins/my_tool/` with a `plugin.py`:

```python
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
    description="Description of my tool",
    ui=ToolUi(kind=UiKind.SCHEMA),  # schema → generic form, no frontend code
    operations=(
        OperationDefinition("echo", Transport.REQUEST_RESPONSE, EchoInput, EchoOutput, echo),
    ),
)
```

- `ui.kind = "schema"` renders via the generic form/result renderer — no frontend code.
- `ui.kind = "custom"` (complex tools): also create `frontend/src/tool_plugins/my_tool/index.tsx`
  whose default export receives a bound `ToolClient` and calls
  `client.invoke(operation, payload)` / `client.connect(operation)`. It is lazy-loaded
  by `import.meta.glob` and reached through the single `/tools/:toolId` route.

2. (Optional, database-backed tools) Add a model inside the plugin directory and write an Alembic migration:

```bash
cd backend
alembic revision -m "add my_tool_records"
# Write the migration by hand (see 002_add_agent_practice_records.py as an example)
alembic upgrade head
```

> **注意**：每个 operation handler 接收注入的 `context.db: AsyncSession`，可直接执行查询；不要在此层 `commit` —— 由 Host 网关统一 commit/rollback。预期业务失败应抛出 `ValidationError` / `NotFoundError` / `ProviderError` 等类型化异常，由 Host 统一转换为 JSON 信封。realtime operation 用 async generator 逐个 `yield` `RealtimeEvent`（`progress` / `delta` / `result`）。参考 `tool_plugins/code_agent_flow_viz/plugin.py` 和 `tool_plugins/chat_tool/plugin.py`。
