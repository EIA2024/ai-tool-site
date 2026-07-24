# Developer Documentation

## Architecture

```
┌──────────────────────┐     REST / WS / SSE      ┌──────────────────────┐
│   Frontend           │◄────────────────────────►│   Backend            │
│   React + Vite + TS  │                          │   Python + FastAPI   │
│   Port 5173          │                          │   Port 8000          │
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

# Install dependencies
pip install -e .
pip install uvicorn[standard]

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api`, `/ws`, and `/sse` to the backend at `localhost:8000`.

### Database

Ensure PostgreSQL and Redis are running locally or via Docker:

```bash
# Start only infra services
docker compose up postgres redis
```

## Verification Checklist

- [ ] **AC-1**: Open http://localhost:5173 → tool list loads → click "Blank Tool" → enter text → submit → see echo response
- [ ] **AC-2**: Open http://localhost:5173 → click "Chat Tool" → click Connect → send message → receive echo reply
- [ ] **AC-3**: Create a new file `backend/app/tools/modules/my_tool.py` extending `BaseTool` → register in `registry.py` → tool appears in the list
- [ ] **AC-4**: Send chat messages → restart backend → reconnect → messages are persisted (check via API)
- [ ] **AC-5**: `docker compose up --build` starts all four services successfully
- [ ] **AC-6**: In non-Docker mode, Vite proxy handles both REST (`/api/tools`) and WebSocket (`/ws/chat`)

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
from app.tools.base import BaseTool

class MyTool(BaseTool):
    tool_id = "my_tool"
    name = "My Tool"
    description = "Description of my tool"
    mode = "request-response"  # or "realtime"

    async def handle_invoke(self, payload: dict) -> dict:
        # Your logic here
        return {"success": True, "data": {"result": "processed"}}
```

2. Register in `backend/app/tools/registry.py`:

```python
from app.tools.modules.my_tool import MyTool
tool_registry.register(MyTool())
```

3. (Optional) Add a frontend page at `frontend/src/pages/tools/MyToolPage.tsx` and update `App.tsx` routes.
