# AI Tool Development Handbook

> 面向开发者和 AI Agent 的 AI Tool Site 开发指南。
> 适用于在此项目骨架基础上开发各种 AI 工具的完整参考。

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Project Map](#2-project-map)
3. [Tool Types](#3-tool-types)
4. [Quickstart: Add Your First Tool](#4-quickstart-add-your-first-tool)
5. [Request-Response Tool Guide](#5-request-response-tool-guide)
6. [Real-Time Tool Guide (WebSocket)](#6-real-time-tool-guide-websocket)
7. [AI API Integration Guide](#7-ai-api-integration-guide)
8. [Database & Persistence Patterns](#8-database--persistence-patterns)
9. [Frontend Component Guide](#9-frontend-component-guide)
10. [Best Practices & Conventions](#10-best-practices--conventions)
11. [Troubleshooting](#11-troubleshooting)
12. [Agent Instructions](#12-agent-instructions)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React + Vite + TS)           │
│  ┌─────────────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │  ToolList (nav)  │  │ ToolPage │  │ ChatToolPage (WS) │  │
│  └────────┬────────┘  └────┬─────┘  └─────────┬─────────┘  │
│           │                │                   │            │
│      ┌────▼────────────────▼───────────────────▼────┐       │
│      │          lib/api.ts  +  lib/ws.ts            │       │
│      │          (HTTP client)   (WS client)          │       │
│      └────────────────────┬─────────────────────────┘       │
└───────────────────────────┼─────────────────────────────────┘
                            │  proxy (Vite dev) / direct (prod)
                            │  /api/*  /ws/*  /sse/*
┌───────────────────────────┼─────────────────────────────────┐
│                    Backend (FastAPI / Python)                │
│  ┌────────────────────────▼─────────────────────────┐       │
│  │              app/api/routes/tools.py              │       │
│  │    GET  /api/tools          → list all tools      │       │
│  │    GET  /api/tools/{id}     → tool detail         │       │
│  │    POST /api/tools/{id}/invoke → run tool         │       │
│  └────────────────────────┬─────────────────────────┘       │
│                           │                                  │
│  ┌────────────────────────▼─────────────────────────┐       │
│  │          app/tools/                              │       │
│  │  ┌──────────┐  ┌──────────────┐  ┌────────────┐  │       │
│  │  │ base.py  │  │ registry.py  │  │ modules/   │  │       │
│  │  │ (ABC)    │  │ (singleton)  │  │ (your tools)│  │       │
│  │  └──────────┘  └──────────────┘  └────────────┘  │       │
│  └───────────────────────────────────────────────────┘       │
│                                                              │
│  ┌────────────────────┐  ┌───────────────────────────────┐   │
│  │  app/ws/handler.py │  │  app/sse/handler.py           │   │
│  │  (WebSocket chat)  │  │  (server-sent events)         │   │
│  └────────────────────┘  └───────────────────────────────┘   │
│                                                              │
│  ┌────────────────────┐  ┌───────────────────────────────┐   │
│  │  PostgreSQL        │  │  Redis                       │   │
│  │  chat_sessions     │  │  session/cache               │   │
│  │  chat_messages     │  │                               │   │
│  │  tool_call_records │  │                               │   │
│  └────────────────────┘  └───────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### Communication Protocols

| Protocol | Path | Use Case |
|---|---|---|
| **REST** | `/api/*` | Request-response tools, CRUD operations, listing |
| **WebSocket** | `/ws/*` | Real-time bidirectional (chat, streaming, live updates) |
| **SSE** | `/sse/*` | Server-to-client event stream (progress, notifications) |

### Three-Layer Tool Architecture

Every tool follows a consistent three-layer pattern:

```
Frontend Page (UI)           ← User interacts here
      ↕  REST API or WebSocket
Backend Tool Module           ← Business logic / AI integration
      ↕  ORM / Service layer
Database (PostgreSQL / Redis) ← Persistence
```

---

## 2. Project Map

```text
ai-tool-site/
│
├── frontend/                          # React + Vite + TypeScript
│   ├── src/
│   │   ├── main.tsx                   # Entry point (BrowserRouter)
│   │   ├── App.tsx                    # Route definitions
│   │   ├── index.css                  # Global styles (dark theme)
│   │   │
│   │   ├── pages/
│   │   │   ├── ToolList.tsx           # Tool navigation (fetches from API)
│   │   │   └── tools/                 # ★ Put your tool pages here
│   │   │       ├── BlankToolPage.tsx  # Request-response template
│   │   │       └── ChatToolPage.tsx   # WebSocket chat template
│   │   │
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Layout.tsx         # Page shell (NavBar + Outlet)
│   │   │   │   └── NavBar.tsx         # Top navigation
│   │   │   └── chat/
│   │   │       ├── ChatMessage.tsx    # Message bubble component
│   │   │       └── ChatInput.tsx      # Message input with send
│   │   │
│   │   ├── lib/
│   │   │   ├── api.ts                 # ★ HTTP client (get/post)
│   │   │   └── ws.ts                  # ★ WebSocket client (auto-reconnect)
│   │   │
│   │   └── types/
│   │       └── index.ts               # ★ Shared TypeScript types
│   │
│   ├── vite.config.ts                 # Dev proxy config
│   ├── Dockerfile                     # Multi-stage build
│   └── package.json
│
├── backend/                           # Python + FastAPI
│   ├── app/
│   │   ├── main.py                    # FastAPI app entry, router includes
│   │   │
│   │   ├── api/
│   │   │   ├── routes/__init__.py     # API router aggregation
│   │   │   └── routes/tools.py        # Tool REST endpoints
│   │   │
│   │   ├── ws/
│   │   │   └── handler.py             # WebSocket connection handler
│   │   │
│   │   ├── sse/
│   │   │   └── handler.py             # SSE event stream
│   │   │
│   │   ├── tools/                     # ★ Tool system
│   │   │   ├── base.py                # BaseTool ABC
│   │   │   ├── registry.py            # ToolRegistry singleton
│   │   │   └── modules/               # ★ Put your tool modules here
│   │   │       ├── blank_tool.py      # Request-response example
│   │   │       └── chat_tool.py       # Real-time example
│   │   │
│   │   ├── models/__init__.py         # SQLAlchemy ORM models
│   │   ├── schemas/__init__.py        # Pydantic schemas
│   │   ├── db/session.py              # Database engine & sessions
│   │   ├── services/
│   │   │   ├── chat_history.py        # Chat persistence CRUD
│   │   │   └── cache.py               # Redis cache wrapper
│   │   └── core/config.py             # Pydantic settings
│   │
│   ├── alembic/                       # Database migrations
│   ├── Dockerfile
│   └── pyproject.toml
│
├── docker-compose.yml                 # Full-stack orchestration
├── .env.example
└── docs/
    ├── development.md                 # Setup instructions
    └── ai-tool-development-handbook.md # ★ This file
```

> Files marked with ★ are your primary extension points.

---

## 3. Tool Types

The framework supports two tool modes defined in `BaseTool.mode`:

| Mode | Value | Communication | Use Cases |
|---|---|---|---|
| **Request-Response** | `"request-response"` | REST API (POST) | Text generation, image generation, data analysis, translation, summary |
| **Real-Time** | `"realtime"` | WebSocket | Chatbots, streaming AI responses, live collaboration, progressive output |

### Mode Decision Guide

```
Your tool needs:
├── One-shot input → output        → request-response
├── Multi-turn conversation        → realtime (WebSocket)
├── Streaming / progressive output → realtime (WebSocket)
├── Server pushes updates          → realtime (SSE)
└── User submits, waits, sees      → request-response
```

---

## 4. Quickstart: Add Your First Tool

The fastest path to add a new AI tool. Takes ~5 minutes.

### Step 1: Backend Module

Create `backend/app/tools/modules/translator.py`:

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.base import BaseTool
from app.core.errors import ValidationError


class TranslatorTool(BaseTool):
    tool_id = "translator"
    name = "AI Translator"
    description = "Translate text between languages using AI"
    mode = "request-response"

    async def handle_invoke(self, payload: dict, db: AsyncSession) -> dict:
        text = payload.get("text", "")
        source_lang = payload.get("source_lang", "auto")
        target_lang = payload.get("target_lang", "English")

        # Raise a typed error for expected business failures; the router
        # turns it into {"success": false, "error": {...}}.
        if not text:
            raise ValidationError("text is required", code="EMPTY_TEXT")

        # ★ Replace with real AI API call (see section 7)
        translated = f"[AI would translate: {text} from {source_lang} to {target_lang}]"

        # Return the success data payload only — no envelope, no commit.
        return {
            "original": text,
            "translated": translated,
            "source_lang": source_lang,
            "target_lang": target_lang,
        }
```

### Step 2: Register

In `backend/app/tools/registry.py`, add the import and register call:

```python
from app.tools.modules.translator import TranslatorTool

tool_registry.register(TranslatorTool())
```

### Step 3: Frontend Page

Create `frontend/src/pages/tools/TranslatorPage.tsx`:

```tsx
import { useState } from "react";
import { post } from "../../lib/api";

export default function TranslatorPage() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const res = await post("/tools/translator/invoke", {
        text,
        target_lang: "English",
      });
      if (res.success && res.data) {
        setResult(JSON.stringify(res.data, null, 2));
      } else {
        setResult(`Error: ${res.error?.message ?? "Unknown"}`);
      }
    } catch (err) {
      setResult(`Request failed: ${String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="tool-page">
      <h2>AI Translator</h2>
      <p>Translate text using AI.</p>
      <div className="input-area">
        <input value={text} onChange={(e) => setText(e.target.value)}
               placeholder="Enter text to translate..." />
        <button onClick={handleSubmit} disabled={loading}>
          {loading ? "Translating..." : "Translate"}
        </button>
      </div>
      {result && <pre className="result-box">{result}</pre>}
    </div>
  );
}
```

### Step 4: Add Route

In `frontend/src/App.tsx`:

```tsx
import TranslatorPage from "./pages/tools/TranslatorPage";

// Inside <Routes>:
<Route path="/tools/translator" element={<TranslatorPage />} />
```

### ✅ Done

The new tool will:
- Appear in the tool list on the home page (auto-discovered from backend)
- Be accessible at `http://localhost:5173/tools/translator`

---

## 5. Request-Response Tool Guide

### Backend: BaseTool Contract

```python
class BaseTool(ABC):
    tool_id: str          # Unique identifier (used in URLs, must match frontend route)
    name: str             # Display name in tool list
    description: str      # Description shown in tool list
    mode: str             # "request-response" or "realtime"

    async def handle_invoke(self, payload: dict, db: AsyncSession) -> dict:
        """Execute the tool for one request.

        Args:
            payload: the tool-specific payload from the client.
            db:     request-scoped async session (injected — never create
                    your own, never commit here).

        Returns:
            The success data payload only. The API layer wraps it in the
            {"success": true, "data": ...} envelope.
        """
        ...
```

### Response Convention

Return the data payload only from `handle_invoke` — no envelope:

```python
# Success — return this dict directly:
{
    "result": "...",           # Primary output
    "metadata": {...},         # Optional: extra info
}

# Error — raise a typed error instead of returning a failure dict:
raise ValidationError("text is required", code="EMPTY_TEXT")
```

The router converts both cases into the standard JSON envelope:

```json
{"success": true,  "data": {...}}
{"success": false, "error": {"code": "VALIDATION_ERROR", "message": "..."}}
```

Available typed errors (see `app/core/errors.py`): `ValidationError`,
`NotFoundError`, `ProviderError` (upstream AI/API failure), `RateLimitError`.
`InternalError` (HTTP 500) is reserved for genuine server bugs — never raise
it from a tool.

### Frontend: Calling the Tool

Use the `invokeTool()` helper from `lib/api.ts` (it wraps the payload in the
`{ "payload": ... }` request body automatically):

```typescript
import { invokeTool } from "../../lib/api";

// POST /api/tools/{tool_id}/invoke
const res = await invokeTool("translator", {
    text: "Hello world",
    target_lang: "French",
});

if (res.success) {
    console.log(res.data);  // typed as T
} else {
    console.error(res.error?.message);
}
```

The POST URL pattern is always `/tools/{tool_id}/invoke` (the `/api` prefix is handled by the client).

---

## 6. Real-Time Tool Guide (WebSocket)

### Backend: WebSocket Handler Pattern

The existing `ws/handler.py` provides a general-purpose chat WebSocket. For tools that need custom WebSocket behavior, create a new endpoint.

Example — add a streaming AI tool WebSocket at `/ws/stream`:

```python
# backend/app/ws/stream_handler.py
import json
import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/stream")
async def stream_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            prompt = json.loads(data).get("prompt", "")

            # Simulate streaming AI response
            for token in prompt.split():
                await websocket.send_text(json.dumps({
                    "type": "token",
                    "content": token + " ",
                }))
                await asyncio.sleep(0.1)  # Simulate delay

            await websocket.send_text(json.dumps({
                "type": "done",
                "content": "",
            }))
    except WebSocketDisconnect:
        logger.info("Client disconnected")
```

Then register the router in `backend/app/main.py`:

```python
from app.ws.stream_handler import router as stream_router
app.include_router(stream_router, prefix="/ws")
```

### Frontend: Using WsClient

The `WsClient` class handles connection lifecycle, exponential backoff
reconnect, and optional session resume:

```typescript
import { useRef, useState } from "react";
import { WsClient } from "../../lib/ws";
import type { WsMessage } from "../../types";

export default function StreamPage() {
  const [messages, setMessages] = useState<string[]>([]);
  const [status, setStatus] = useState("disconnected");
  const clientRef = useRef<WsClient | null>(null);

  const connect = (sessionId?: string) => {
    const client = new WsClient(
      (msg) => setMessages((prev) => [...prev, msg.content]),
      setStatus
    );
    clientRef.current = client;
    client.connect(sessionId);   // pass ?session_id= to resume a chat session
  };

  const sendPrompt = (text: string) => {
    clientRef.current?.send(text);
  };

  const disconnect = () => clientRef.current?.disconnect();

  // ...render connect button, messages, input
}
```

The `WsClient` auto-reconnects with backoff (1s → 30s max) after an
unexpected close; call `disconnect()` on unmount to stop it.

### WebSocket Message Envelope

```typescript
// Frontend sends:
{ "type": "message", "content": "user input" }

// Backend responds:
{ "type": "connected", "session_id": "..." }   // first frame, before any echo
{ "type": "message",
  "content": "Echo: user input",
  "sender": "assistant",
  "timestamp": "2026-07-25T12:00:00Z" }
{ "type": "error", "message": "content exceeds 10000 chars" }
```

---

## 7. AI API Integration Guide

The project uses the **DeepSeek API**. Configuration lives in
`backend/app/core/config.py` (`deepseek_api_key`, `deepseek_models`,
`deepseek_default_model`). A complete, production-shaped reference is the
[Task Decomposer](backend/app/tools/modules/task_decomposer.py) tool: prompt
building and the API call live in a self-contained client module
(`task_decomposer_client.py`), failures are wrapped as `ProviderError`, and
the response is validated with Pydantic.

### Pattern: Direct API Call (Request-Response)

```python
import httpx

from app.core.config import settings
from app.core.errors import ProviderError, ValidationError

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


class SummarizerTool(BaseTool):
    tool_id = "summarizer"
    name = "AI Summarizer"
    description = "Summarize text using AI"
    mode = "request-response"

    async def handle_invoke(self, payload: dict, db: AsyncSession) -> dict:
        text = payload.get("text", "")
        if not text:
            raise ValidationError("text is required", code="EMPTY_TEXT")

        body = {
            "model": payload.get("model") or settings.deepseek_default_model,
            "messages": [
                {"role": "system", "content": "Summarize the following text."},
                {"role": "user", "content": text},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": 2200,
        }
        headers = {
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(DEEPSEEK_URL, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise ProviderError("无法连接 DeepSeek API", code="DEEPSEEK_ERROR") from exc

        if response.status_code >= 400:
            raise ProviderError(
                f"DeepSeek API 返回错误：HTTP {response.status_code}",
                code="DEEPSEEK_ERROR",
            )

        try:
            payload = response.json()
            summary = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("DeepSeek 返回结构异常", code="DEEPSEEK_ERROR") from exc

        return {"summary": summary, "model": body["model"]}
```

Key rules:

- **Never return an error dict** — raise `ProviderError` (or `ValidationError`
  for bad input). The router converts it into the standard envelope.
- **Never let exceptions escape raw** — wrap network / HTTP / parse failures
  in `ProviderError` so the client gets a typed, structured error.
- **Validate the model response** with a Pydantic schema before using it
  (see `ModelTaskAnalysis` in `task_decomposer_client.py`).

### Pattern: Streaming via WebSocket

For streaming AI responses (ChatGPT-style), use WebSocket to push tokens
progressively. The existing `ws/handler.py` shows the session/persistence
pattern; a streaming tool would send `{"type": "token", "content": ...}`
frames from an `httpx.AsyncClient.stream` loop and finish with a `done` frame:

```python
import json
import httpx
from fastapi import WebSocket


async def stream_ai_response(websocket: WebSocket, prompt: str, api_key: str):
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "deepseek-v4-flash",
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
            },
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    chunk = json.loads(line[6:])
                    delta = chunk["choices"][0].get("delta", {}).get("content", "")
                    if delta:
                        await websocket.send_text(json.dumps({
                            "type": "token",
                            "content": delta,
                        }))

    await websocket.send_text(json.dumps({"type": "done", "content": ""}))
```

### Environment Variables for AI APIs

Add the API key to `backend/.env` (never commit to git) — or the repo root
`.env` used by Docker Compose:

```ini
# backend/.env
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODELS=deepseek-v4-flash,deepseek-v4-pro
DEEPSEEK_DEFAULT_MODEL=deepseek-v4-flash
```

These fields already exist in `Settings` (`backend/app/core/config.py`). The
frontend reads the model list from `GET /api/config`, so a new model added
here is picked up without a frontend rebuild.

### Using the Cache Layer

```python
from app.services.cache import cache_get, cache_set

# Cache AI response for 1 hour
cache_key = f"summary:{hash(text)}"
cached = await cache_get(cache_key)
if cached:
    return cached

result = await call_ai_api(text)
await cache_set(cache_key, result, ttl=3600)
return result
```

---

## 8. Database & Persistence Patterns

### Existing Models

```python
# backend/app/models/__init__.py

class ChatSession(Base):
    """A conversation session. Each WebSocket chat creates one."""
    __tablename__ = "chat_sessions"
    id, title, tool_id, created_at, updated_at

class ChatMessage(Base):
    """A single message in a chat session."""
    __tablename__ = "chat_messages"
    id, session_id, role, content, created_at

class ToolCallRecord(Base):
    """Log of tool invocation (for audit/history)."""
    __tablename__ = "tool_call_records"
    id, tool_id, input_data, output_data, success, created_at
```

### Adding a New Model

For tool-specific data, add models to `backend/app/models/__init__.py`:

```python
class TranslationRecord(Base):
    __tablename__ = "translation_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_lang: Mapped[str] = mapped_column(String(50))
    target_lang: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

Then create an Alembic migration:

```bash
cd backend
alembic revision --autogenerate -m "add translation_records"
alembic upgrade head
```

### Recording Tool Calls

Every tool invocation is audited **automatically** by the API layer
(`app/api/routes/tools.py` → `app/services/audit.py::log_tool_call`): the
input payload, output data, and success flag are written to
`tool_call_records` on every call — success or failure. You can view the log
via `GET /api/audit/tool-calls`. Tools never write audit records themselves.

For tool-specific data (your own tables), use the **injected** `db` session
and **never commit** inside the tool:

```python
# In your tool's handle_invoke — db is injected, no session factory needed:
record = TranslationRecord(
    source_text=text,
    translated_text=translated,
    source_lang=source_lang,
    target_lang=target_lang,
)
db.add(record)
# No await db.commit() here! The router commits exactly once per request.
```

This is the unit-of-work rule: services and tools `add`/`flush`, the router
`commit`s once, and any expected failure (typed error) triggers a single
`rollback`. If your tool must swallow a failure and keep going (e.g. a
best-effort history save), do `await db.rollback()` explicitly first — see
`_analyze_task` in `task_decomposer.py`.

---

## 9. Frontend Component Guide

### Available Components

| Component | File | Usage |
|---|---|---|
| `Layout` | `components/layout/Layout.tsx` | Page shell with NavBar |
| `NavBar` | `components/layout/NavBar.tsx` | Top navigation bar (add tool links here) |
| `ChatMessage` | `components/chat/ChatMessage.tsx` | Message bubble (sender + content) |
| `ChatInput` | `components/chat/ChatInput.tsx` | Text input with Send button + Enter to send |

### Styling

Use CSS classes from `index.css`. Available utility classes:

- `.tool-page` — standard tool page wrapper
- `.input-area` — input + button row
- `.result-box` — preformatted output display
- `.chat-messages` — scrollable message container
- `.chat-message` — single message (.message-user / .message-bot)
- `.status-text` — centered status text
- `.ws-status` — WebSocket connection status badge (.status-connected / .status-disconnected)

### TypeScript Types

```typescript
// types/index.ts
interface ToolMeta { tool_id, name, description, mode, config? }
interface ApiResponse<T> { success, data?, error? }
interface WsMessage { type, content, sender, timestamp, session_id? }
```

---

## 10. Best Practices & Conventions

### Backend

- **One file per tool module** in `backend/app/tools/modules/`
- **tool_id** uses `snake_case` (e.g., `image_generator`, `code_reviewer`)
- **Keep `handle_invoke` focused**: validate input, call AI/external API, return the data payload
- **Error handling**: raise typed errors (`ValidationError`, `NotFoundError`, `ProviderError`) instead of returning failure dicts; never let raw exceptions escape
- **DB access**: use the injected `db: AsyncSession`; never open your own session and never `commit` inside a tool (unit-of-work — the router commits once)
- **Async IO**: use `httpx.AsyncClient` for HTTP calls, not `requests`
- **Secrets**: never hardcode API keys; use `Settings` from `config.py`

### Frontend

- **One file per tool page** in `frontend/src/pages/tools/`
- **Route path** matches `tool_id` (e.g., `tool_id = "code_reviewer"` → route `/tools/code_reviewer`)
- **Use `lib/api.ts`** for REST calls, **`lib/ws.ts`** for WebSocket
- **Loading state**: always track loading state to disable buttons during requests
- **Error display**: show `res.error?.message` when a request fails

### Adding Tools Checklist

- [ ] Backend module created in `tools/modules/`
- [ ] Registered in `tools/registry.py`
- [ ] Frontend page created in `pages/tools/`
- [ ] Route added in `App.tsx`
- [ ] (Optional) NavBar link added in `components/layout/NavBar.tsx`
- [ ] (Optional) Database model and migration for tool-specific data
- [ ] Backend starts without error: `python -c "from app.main import app"`
- [ ] Frontend builds without error: `npm run build`

---

## 11. Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Backend crashes on start | Import error in config.py | Check `from app.core.config import settings` works |
| Tool not appearing in list | Not registered in `registry.py` | Add `tool_registry.register(YourTool())` |
| Frontend can't reach backend | Docker not running / CORS | Use Vite proxy for dev; check `docker compose ps` |
| WebSocket disconnects | ConnectionManager not tracking | Ensure `connect()`/`disconnect()` are paired |
| Alembic migration fails | Async URL in sync context | `env.py` auto-strips `+asyncpg` — check `alembic.ini` |
| `ModuleNotFoundError` for tools | Missing `__init__.py` | All module directories need `__init__.py` |
| Docker frontend shows blank page | Volume mount overrides dist | Use `docker compose up --build` to rebuild |

### Quick Diagnostic Commands

```bash
# Backend health
curl http://localhost:8000/api/health

# Tool list
curl http://localhost:8000/api/tools

# Frontend build check
cd frontend && npm run build

# Python import check
cd backend && python -c "from app.main import app; print('OK')"

# Lint
cd backend && ruff check .
```

---

## 12. Agent Instructions

> This section is for AI Agents (Claude Code, Codex, etc.) working on this project.

### Project Entry Points

When starting work on this project, read in this order:

```text
1. CLAUDE.md               — Workflow protocol instructions
2. AGENTS.md               — Cross-agent workflow bootstrap
3. .workflow/              — Prompt-driven workflow system
4. docs/development.md     — Setup guide
5. docs/ai-tool-development-handbook.md  — This file
```

### Understanding the Codebase

Key architectural invariants:

- **The tool registry is the central hub**: `backend/app/tools/registry.py` lists all available tools. The frontend tool list is dynamically generated from the backend `/api/tools` endpoint, so registration alone makes a tool visible.
- **`BaseTool` is the contract**: every tool module must subclass `BaseTool` and implement `handle_invoke()`. The `tool_id` field must be a unique `snake_case` string.
- **Frontend routes must match `tool_id`**: the route path in `App.tsx` must use underscores (e.g., `tool_id = "my_tool"` → route `/tools/my_tool`).
- **Two communication modes**: `request-response` tools use REST POST; `realtime` tools use WebSocket. Choose based on whether the interaction is single-turn or multi-turn/streaming.

### Adding a Tool (Agent Workflow)

When asked to add a new AI tool:

1. **Clarify intent**: Determine tool type (request-response or realtime), inputs, outputs, AI API requirements.
2. **Create backend module**: New file in `backend/app/tools/modules/`.
3. **Register**: Add import and `register()` call in `registry.py`.
4. **Create frontend page**: New file in `frontend/src/pages/tools/`.
5. **Add route**: Add `<Route>` in `App.tsx`.
6. **Verify**: Run `cd backend && python -c "from app.main import app"` and `cd frontend && npm run build`.

### Common Patterns to Follow

- Each tool is self-contained: one backend module + one frontend page
- Use existing examples as templates (`BlankToolPage` for request-response, `ChatToolPage` for real-time)
- API keys and environment-specific config go in `backend/app/core/config.py` using `pydantic-settings`
- Database operations use the **injected** async session (`db: AsyncSession` parameter of `handle_invoke`) — never `app.db.session.async_session_factory` inside a tool, and never commit there
- Cache operations use `app.services.cache.cache_get/cache_set`

---

*Last updated: 2026-07-25*
*Maintainer: EIA2024*
