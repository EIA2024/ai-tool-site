# AI Tool Development Handbook

> 面向开发者和 AI Agent 的 AI Tool Site 开发指南。
> 适用于在此项目骨架基础上开发各种 AI 工具的完整参考。

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Project Map](#2-project-map)
3. [Tool Types](#3-tool-types)
4. [Quickstart: Add Your First Tool](#4-quickstart-add-your-first-tool)
5. [Request-Response Operation Guide](#5-request-response-operation-guide)
6. [Real-Time Operation Guide](#6-real-time-operation-guide)
7. [AI API Integration Guide](#7-ai-api-integration-guide)
8. [Database & Persistence Patterns](#8-database--persistence-patterns)
9. [Frontend Plugin Guide](#9-frontend-plugin-guide)
10. [Best Practices & Conventions](#10-best-practices--conventions)
11. [Troubleshooting](#11-troubleshooting)
12. [Agent Instructions](#12-agent-instructions)

---

## 1. Architecture Overview

The site is a **single-repo Host + Plugins** architecture. The website ("Host") owns
the Dock, dynamic routing, unified protocol, model/keys, database, rate limiting,
audit and error handling. Tools are **auto-discovered** from
`backend/app/tool_plugins/<tool_id>/` — adding a tool never edits `App.tsx`,
navigation, or a central registry; a frontend rebuild + backend restart makes it live.

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React + Vite + TS)           │
│  ┌──────────┐  ┌───────────┐  ┌─────────────────────────┐   │
│  │ Dock     │  │ /tools/:id│  │ schema renderer         │   │
│  │ ToolList │  │ ToolPage  │  │ + tool_plugins/*/index  │   │
│  └────┬─────┘  └─────┬─────┘  └───────────┬─────────────┘   │
│       └──────────────┴────────┬────────────┘                 │
│                     lib/toolClient.ts  (invoke / connect)     │
└───────────────────────────────┼─────────────────────────────┘
                                │  /api/tools/*   /ws/tools/*
┌───────────────────────────────┼─────────────────────────────┐
│                      Backend (FastAPI / Python)              │
│  ┌────────────────────────────▼───────────────────────────┐  │
│  │ app/tool_host/  Host runtime                          │  │
│  │  contracts.py   ToolManifest / ToolPlugin / RealtimeEvent │
│  │  discovery.py   scans app/tool_plugins/*/plugin.py     │  │
│  │  routes.py      GET /api/tools, POST /api/tools/{id}/operations/{op} │
│  │  websocket.py   WS /ws/tools/{id}/operations/{op}      │  │
│  │  runtime.py     input/output validation + dispatch     │  │
│  │  site.py        Dock order + hidden list               │  │
│  └────────────────────────────┬───────────────────────────┘  │
│  ┌────────────────────────────▼───────────────────────────┐  │
│  │ app/tool_plugins/<tool_id>/  (your tools)              │  │
│  │   plugin.py     manifest + Pydantic handlers           │  │
│  │   models.py / repository.py (persistence, optional)    │  │
│  └────────────────────────────────────────────────────────┘  │
│  app/services/ (llm, audit, cache)   app/models/ (audit)     │
│  app/core/ (config, errors, ratelimit, redact)  app/db/      │
└──────────────────────────────────────────────────────────────┘
```

### Unified Protocol

| Protocol | Path | Use Case |
|---|---|---|
| **REST** | `GET /api/tools`, `GET /api/tools/{id}`, `POST /api/tools/{id}/operations/{op}` | discovery + request-response operations |
| **WebSocket** | `/ws/tools/{id}/operations/{op}` | realtime operations (streaming) |

Every operation declares a `transport` (`request-response` or `realtime`) and
Pydantic input/output models; the Host validates input, runs the handler,
validates output, and commits/rolls back exactly once per request.

---

## 2. Project Map

```text
ai-tool-site/
│
├── frontend/                          # React + Vite + TypeScript
│   ├── src/
│   │   ├── App.tsx                    # Routes: /, /usage, /tools/:toolId
│   │   ├── pages/
│   │   │   ├── ToolList.tsx           # Dock (auto from GET /api/tools)
│   │   │   ├── ToolPage.tsx           # dynamic route → schema vs custom dispatch
│   │   │   └── schema/SchemaTool.tsx  # generic form/result renderer
│   │   ├── lib/
│   │   │   ├── api.ts                 # get/post/del + ApiError
│   │   │   ├── toolClient.ts          # ★ createToolClient (invoke/connect)
│   │   │   └── realtime.ts            # RealtimeClient (frame protocol)
│   │   ├── types/index.ts             # Host–Plugin contract types
│   │   └── tool_plugins/              # ★ custom UI per tool
│   │       ├── registry.ts            # import.meta.glob map (tool_id → UI)
│   │       ├── chat_tool/index.tsx
│   │       ├── code_agent_flow_viz/index.tsx
│   │       └── task_decomposer/index.tsx
│   ├── vitest.config.ts               # Vitest (jsdom)
│   ├── vite.config.ts
│   └── package.json
│
├── backend/                           # Python + FastAPI
│   ├── app/
│   │   ├── tool_host/                 # Host runtime (contracts/discovery/routes/websocket/…)
│   │   ├── tool_plugins/              # ★ your tools
│   │   │   ├── blank_tool/plugin.py   # hidden schema example
│   │   │   ├── chat_tool/plugin.py    # realtime example
│   │   │   ├── code_agent_flow_viz/plugin.py  # request-response + persistence
│   │   │   └── task_decomposer/plugin.py      # request-response + LLM
│   │   ├── api/routes/audit.py        # site-level audit endpoints
│   │   ├── services/                  # llm.py, audit.py, cache.py (Host-owned)
│   │   ├── models/                    # audit model (Host-owned)
│   │   ├── core/                      # config, errors, ratelimit, redact
│   │   └── db/session.py
│   ├── alembic/                       # migrations
│   └── pyproject.toml
│
├── docker-compose.yml
└── docs/
```

> Files marked with ★ are your primary extension points.

---

## 3. Tool Types

Tools are distinguished by the **transport of each operation** declared in the
manifest — not by a top-level "mode":

| Transport | Value | Communication | Use Cases |
|---|---|---|---|
| **request-response** | `request-response` | REST `POST /api/tools/{id}/operations/{op}` | one-shot input → output |
| **realtime** | `realtime` | WebSocket `/ws/tools/{id}/operations/{op}` | streaming, multi-turn |

A single plugin can mix both (the chat plugin has `list_sessions` as
request-response and `send_message` as realtime).

### `ui.kind` Decision Guide

```
Your tool's frontend:
├── Simple form → result      → ui.kind = "schema"   (generic renderer, no frontend code)
├── Complex / bespoke UI      → ui.kind = "custom"   (tool_plugins/<id>/index.tsx)
```

`ui.layout` is `"standard"` (wrapped in the site NavBar) or `"fullscreen"`
(the plugin draws its own chrome and back link).

---

## 4. Quickstart: Add Your First Tool

The fastest path to add a new AI tool. Takes ~5 minutes, no Host edits.

### Step 1: Backend plugin

Create `backend/app/tool_plugins/translator/plugin.py`:

```python
from pydantic import BaseModel, Field

from app.tool_host.contracts import (
    OperationDefinition, ToolContext, ToolPlugin, ToolUi, Transport, UiKind,
)


class TranslateInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    target_lang: str = Field(default="English", max_length=50)


class TranslateOutput(BaseModel):
    original: str
    translated: str
    target_lang: str


async def translate(payload: TranslateInput, context: ToolContext) -> TranslateOutput:
    # ★ Replace with a real AI call (see section 7).
    translated = f"[AI would translate: {payload.text} to {payload.target_lang}]"
    return TranslateOutput(
        original=payload.text,
        translated=translated,
        target_lang=payload.target_lang,
    )


plugin = ToolPlugin(
    id="translator",
    version="1.0.0",
    name="AI Translator",
    description="Translate text between languages using AI",
    ui=ToolUi(kind=UiKind.SCHEMA),  # schema → generic form, no frontend code
    operations=(
        OperationDefinition(
            "translate", Transport.REQUEST_RESPONSE, TranslateInput, TranslateOutput, translate
        ),
    ),
)
```

### Step 2: Rebuild & restart

Restart the backend and rebuild the frontend. That's it — the tool appears in
the Dock (auto-discovered), reachable at `/tools/translator`, and rendered by the
generic schema form because `ui.kind = "schema"`.

### Step 3 (optional): custom frontend

For a complex UI, set `ui.kind = "custom"` and add
`frontend/src/tool_plugins/translator/index.tsx`:

```tsx
import { useState } from "react";
import type { ToolPluginProps } from "../../types";

export default function TranslatorPlugin({ client }: ToolPluginProps) {
  const [result, setResult] = useState<string | null>(null);

  const run = async () => {
    const res = await client.invoke("translate", { text: "Hello", target_lang: "French" });
    setResult(res.success ? JSON.stringify(res.data, null, 2) : res.error?.message ?? "Error");
  };

  return (
    <div className="tool-page">
      <h2>AI Translator</h2>
      <button onClick={run}>Translate</button>
      {result && <pre className="result-box">{result}</pre>}
    </div>
  );
}
```

The custom component is lazy-loaded by `import.meta.glob` and reached through the
single `/tools/:toolId` route — no `App.tsx` or `NavBar` edits.

---

## 5. Request-Response Operation Guide

### Backend: OperationDefinition contract

```python
OperationDefinition(
    "translate",                        # operation id (snake_case)
    Transport.REQUEST_RESPONSE,         # transport
    TranslateInput,                     # Pydantic input model (validated by Host)
    TranslateOutput,                    # Pydantic output model (validated by Host)
    translate,                          # async handler: (input, ToolContext) -> output
)
```

The handler receives `context.db: AsyncSession` (injected — never create your
own, never commit here). Return the output model directly; the Host wraps it in
`{"success": true, "data": {...}}`. Raise a typed error for expected failures.

```python
# Success — return the output model:
return TranslateOutput(original=..., translated=..., target_lang=...)

# Error — raise a typed error instead of returning a failure:
raise ValidationError("text is required", code="EMPTY_TEXT")
```

The Host converts both into the standard envelope:

```json
{"success": true,  "data": {...}}
{"success": false, "error": {"code": "VALIDATION_ERROR", "message": "..."}}
```

Available typed errors (see `app/core/errors.py`): `ValidationError`,
`NotFoundError`, `ProviderError` (upstream AI/API failure), `RateLimitError`.
`InternalError` (HTTP 500) is reserved for genuine server bugs — never raise it
from a handler.

### Frontend: calling an operation

Custom plugins receive a bound `ToolClient` and call `invoke(operation, payload)`
— they never build URLs:

```tsx
const res = await client.invoke("translate", { text: "Hello", target_lang: "French" });
if (res.success) console.log(res.data);
else console.error(res.error?.message);
```

`invoke` POSTs `{ "payload": {...} }` to `/api/tools/{id}/operations/{op}`.

---

## 6. Real-Time Operation Guide

### Backend: realtime handler

A realtime operation's handler is an **async generator** that `yield`s
`RealtimeEvent`s. The Host streams them over WebSocket and enforces the frame
protocol.

```python
from app.tool_host.contracts import RealtimeEvent

async def stream_tokens(payload: StreamInput, context: ToolContext):
    request_id = context.request_id or ""
    yield RealtimeEvent(type="progress", request_id=request_id, data={"stage": "start"})
    async for delta in produce_tokens(payload.prompt):
        yield RealtimeEvent(type="delta", request_id=request_id, data={"content": delta})
    yield RealtimeEvent(type="result", request_id=request_id, data={"done": True})
```

The gateway emits a `ready` frame on connect, then for each `invoke` streams the
generator's `progress` / `delta` / `result` events, validates the `result` against
the output model, commits once, and audits. On a typed error it sends an `error`
frame and keeps the socket open.

### Frontend: using `client.connect`

```tsx
const conn = client.connect("stream");
conn.onEvent((event) => {
  if (event.type === "delta") append(event.data.content);
  else if (event.type === "result") finish(event.data);
  else if (event.type === "error") show(event.data.message);
});
conn.onStatus((status) => setStatus(status));
conn.open();
conn.send({ prompt: "hello" });  // sends {type:"invoke", request_id, payload}
```

### WebSocket frame protocol

```
client → server:  { "type": "invoke", "request_id": "...", "payload": {...} }
server → client:  { "type": "ready", "tool_id": "...", "operation_id": "..." }
                  { "type": "progress" | "delta" | "result" | "error", "request_id": "...", "data": {...} }
```

---

## 7. AI API Integration Guide

The project talks to models through a **provider abstraction layer**
(`backend/app/services/llm.py`). Providers are config-driven: the default is
DeepSeek, and adding another OpenAI-compatible provider (OpenAI, GLM, Moonshot,
Kimi, Qwen, ...) is one `LLM_PROVIDERS` entry plus one Settings field for its API
key — no client code. New tools call `chat_completion` (request-response) or
`chat_completion_stream` (realtime) instead of talking to httpx directly. A
complete, production-shaped reference is the
[Task Decomposer](../backend/app/tool_plugins/task_decomposer/client.py) plugin:
prompt building lives in `client.py`, upstream failures are caught as the shared
`ProviderError` and re-wrapped as the HTTP-layer error type, and the response is
validated with Pydantic.

### Pattern: request-response

```python
from app.core.errors import ProviderError as HttpProviderError, ValidationError
from app.services.llm import ProviderError as LlmProviderError, chat_completion, get_default_model


async def summarize(payload: SummarizeInput, context: ToolContext) -> SummarizeOutput:
    if not payload.text:
        raise ValidationError("text is required", code="EMPTY_TEXT")
    model = payload.model or get_default_model()
    try:
        summary = await chat_completion(
            [{"role": "system", "content": "Summarize the following text."},
             {"role": "user", "content": payload.text}],
            model,
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=2200,
        )
    except LlmProviderError as exc:
        raise HttpProviderError(str(exc), code="LLM_ERROR") from exc
    return SummarizeOutput(summary=summary, model=model)
```

Key rules:

- **Never return an error dict** — raise `ValidationError` / `ProviderError`.
- **Two-layer error model** — `app.services.llm.ProviderError` (carries
  `.retryable`) is caught and re-raised as `app.core.errors.ProviderError` with
  `code="LLM_ERROR"`. Don't let either leak raw.
- **Validate the model response** with a Pydantic schema (see
  `task_decomposer/client.py`).

### Pattern: streaming

Realtime operations wrap `chat_completion_stream` and yield `delta` events — see
`tool_plugins/chat_tool/plugin.py::send_message` for the session/persistence
pattern, including the `finally: await stream.aclose()` teardown.

### Environment variables

Add the API key to `backend/.env` (never commit), e.g. `DEEPSEEK_API_KEY=sk-...`.
Everything the app knows about models comes from `Settings.llm_providers`
(`backend/app/core/config.py`); the frontend reads `GET /api/config`
(`models` / `default_model`), so a new model/provider is picked up without a
frontend rebuild.

### Adding a model provider

Configuration only — no code change:

1. Declare its key as a Settings field (e.g. `glm_api_key: str = ""`).
2. Add it to `LLM_PROVIDERS` (JSON list) with `id` / `name` / `base_url` /
   `api_key_env` / `models` / `default_model` / `supports_thinking`.

Restart the backend; `GET /api/config` advertises the new models.

### Cache layer

```python
from app.services.cache import cache_get, cache_set
cached = await cache_get(key)
if cached: return cached
result = await call_ai_api(...)
await cache_set(key, result, ttl=3600)
```

---

## 8. Database & Persistence Patterns

### Existing models

Host-owned: `ToolCallRecord` (`app/models/audit.py`). Plugin-owned models live in
their plugin directory (e.g. `tool_plugins/chat_tool/models.py` for
`ChatSession` / `ChatMessage`, `tool_plugins/code_agent_flow_viz/models.py` for
`AgentPracticeRecord`).

### Adding a model

Add tool-specific models **inside your plugin directory** (they are registered on
`Base.metadata` when plugin discovery imports the plugin), then write an Alembic
migration — discovery does not auto-create tables:

```bash
cd backend
alembic revision -m "add translation_records"
# Write the migration by hand (see 002_add_agent_practice_records.py)
alembic upgrade head
```

### Recording tool calls

Every operation is audited **automatically** by the Host
(`app/tool_host/gateway.py` → `app/services/audit.py::log_tool_call`): input,
output, and success flag are written to `tool_call_records` on every call.
`GET /api/audit/summary` exposes aggregate usage. Anonymous
`GET /api/audit/tool-calls` responses keep the record metadata but return
`input_data` / `output_data` as `null`; raw details require
`include_details=true` and a bearer token matching `AUDIT_OPERATOR_TOKEN`.
Handlers never write audit records themselves.

For your own tables, use the **injected** `context.db` and **never commit**
inside the handler — the Host commits once per request. If your handler must
swallow a failure and keep going (e.g. best-effort history save), call
`await context.db.rollback()` explicitly first — see
`tool_plugins/task_decomposer/plugin.py::analyze_task`.

---

## 9. Frontend Plugin Guide

### Site-level pieces (Host)

| Piece | File | Role |
|---|---|---|
| `ToolList` | `pages/ToolList.tsx` | Dock, generated from `GET /api/tools` |
| `ToolPage` | `pages/ToolPage.tsx` | dynamic `/tools/:toolId`, schema vs custom dispatch |
| `SchemaTool` | `pages/schema/SchemaTool.tsx` | generic form/result renderer |
| `PluginMissing` | `pages/PluginMissing.tsx` | compatibility error when a custom tool has no UI |
| `toolClient` | `lib/toolClient.ts` | `createToolClient` → `invoke` / `connect` |

### Custom plugin contract

A custom plugin's `tool_plugins/<id>/index.tsx` default-exports a component
receiving `{ client, manifest }`. It calls `client.invoke(operation, payload)` or
`client.connect(operation)` and is lazy-loaded by `import.meta.glob`.

### Styling

Use the classes in `src/index.css`. Common ones: `.tool-page`, `.input-area`,
`.result-box`, `.status-text`, `.error-text`, plus the `viz-*` / `td-*` scoped
themes already defined for the flow visualizer and task decomposer.

---

## 10. Best Practices & Conventions

### Backend

- **One plugin directory per tool** in `backend/app/tool_plugins/<tool_id>/`
- **`id`** uses `snake_case` (e.g. `image_generator`, `code_reviewer`)
- **Keep handlers focused**: validate (via Pydantic), call AI/external API, return the output model
- **Error handling**: raise typed errors (`ValidationError`, `NotFoundError`, `ProviderError`) instead of returning failure dicts
- **DB access**: use the injected `context.db`; never open your own session and never `commit` inside a handler (unit-of-work — the Host commits once)
- **Async IO**: use `httpx` (via `app.services.llm`), not `requests`
- **Secrets**: never hardcode API keys; use `Settings` from `config.py`

### Frontend

- **One directory per tool UI** in `frontend/src/tool_plugins/<tool_id>/`
- **Use the bound `ToolClient`** (`client.invoke` / `client.connect`), never hand-build URLs
- **Loading state**: always track loading state to disable buttons during requests
- **Error display**: show `res.error?.message` when a request fails

### Adding Tools Checklist

- [ ] `backend/app/tool_plugins/<id>/plugin.py` with a `ToolPlugin` (manifest + operations)
- [ ] (Optional) `frontend/src/tool_plugins/<id>/index.tsx` for `ui.kind = "custom"`
- [ ] (Optional) DB model inside the plugin + Alembic migration
- [ ] Backend starts without error: `python -c "from app.main import app"`
- [ ] Frontend builds without error: `npm run build`

---

## 11. Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Backend crashes on start | invalid manifest / duplicate id / handler-transport mismatch | discovery fails fast — read the startup error |
| Tool not appearing in Dock | hidden in `tool_host/site.py` or plugin failed discovery | check `HIDDEN_TOOL_IDS` / backend logs |
| Frontend can't reach backend | Docker not running / CORS | use Vite proxy for dev; check `docker compose ps` |
| Custom tool shows "没有找到对应的插件" | `ui.kind = "custom"` but no `tool_plugins/<id>/index.tsx` | add the UI entry, or set `ui.kind = "schema"` |
| Alembic migration fails | async URL in sync context | `env.py` auto-strips `+asyncpg` |
| `ModuleNotFoundError` for a plugin | missing `__init__.py` / plugin.py | each plugin dir needs `__init__.py` + `plugin.py` exporting `plugin` |

### Quick diagnostic commands

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/tools
cd backend && python -c "from app.main import app; print('OK')"
cd frontend && npm run build
cd frontend && npm run test
```

---

## 12. Agent Instructions

> This section is for AI Agents (Claude Code, Codex, etc.) working on this project.

### Key architectural invariants

- **Plugins are auto-discovered** from `backend/app/tool_plugins/*/plugin.py`; the Dock and routes are generated from `GET /api/tools`. Registration is not explicit.
- **`ToolPlugin` is the contract**: `id` (snake_case), `version`, `ui` (`kind`/`layout`), and a tuple of `OperationDefinition`s. Each operation declares `transport` + Pydantic input/output models + a handler.
- **Handlers never commit** — the Host validates input, runs the handler, validates output, commits once, and audits.
- **realtime handlers are async generators** yielding `RealtimeEvent`s; request-response handlers are coroutines returning the output model.
- **Frontend plugins receive a bound `ToolClient`** and call `invoke(operation, payload)` / `connect(operation)`; custom UIs are lazy-loaded via `import.meta.glob` through the single `/tools/:toolId` route.

### Adding a tool (agent workflow)

1. **Clarify intent**: transport (request-response vs realtime), inputs/outputs, AI API requirements, frontend complexity.
2. **Create the plugin dir** `backend/app/tool_plugins/<id>/` with `plugin.py` (manifest + handlers).
3. **(Optional, persistence)** add `models.py`/`repository.py` + an Alembic migration.
4. **(Optional, custom UI)** add `frontend/src/tool_plugins/<id>/index.tsx` (schema tools need none).
5. **Verify**: `python -m pytest -q`, `alembic check`, `npm run test`, `npm run build`.

### Templates to copy

- `blank_tool/plugin.py` — hidden schema example (request-response `echo`)
- `code_agent_flow_viz/plugin.py` — request-response + persistence (CRUD operations)
- `chat_tool/plugin.py` — realtime (`send_message` async generator) + session CRUD
- `task_decomposer/plugin.py` — request-response + LLM (provider error wrapping)

---

*Last updated: 2026-08-13*
*Maintainer: EIA2024*
