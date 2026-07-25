---
workflow_id: WF-20260725-task-decomposer-A3E1
status: DRAFT
based_on_commit: 27727ae
author_role: CLAUDE_CONTEXT_SCOUT
---

# Project Context

## Project Summary (AI Tool Site)

- **Purpose**: AI Tool Site — a web application hosting a collection of AI-powered tools. Users navigate a tool grid, select a tool, and interact via REST API.
- **Primary users**: Developers practicing prompt-crafting and AI agent interaction workflows.
- **Main user flow**: Homepage → tool grid → select a tool → interact (request-response) → see results.

## Relevant Structure (AI Tool Site)

| Path or component | Responsibility | Relevance |
|---|---|---|
| `backend/app/tools/base.py` | BaseTool ABC — contract for all tool modules | Must subclass for new tool |
| `backend/app/tools/registry.py` | ToolRegistry — singleton that registers and lists tools | Must register new tool here |
| `backend/app/tools/modules/` | Directory for tool module implementations | New tool module goes here |
| `backend/app/api/routes/tools.py` | REST endpoints: GET/POST /api/tools/{id}/invoke | Auto-handles registered tools |
| `frontend/src/pages/tools/` | Frontend page implementations for each tool | New tool page goes here |
| `frontend/src/App.tsx` | Route definitions | Must add route for new tool |
| `frontend/src/pages/ToolList.tsx` | Dynamic tool list (fetches from GET /api/tools) | Auto-discovers registered tools |
| `frontend/src/lib/api.ts` | HTTP client (`get`/`post` helpers) | Used by frontend tool pages |
| `frontend/src/types/index.ts` | TypeScript type definitions (ToolMeta, ApiResponse) | Type definitions for tools |
| `frontend/src/index.css` | Global styles with dark theme | Tool pages use existing CSS classes |
| `backend/app/core/config.py` | Pydantic-settings for env vars (API keys, DB, Redis) | Used for DeepSeek API key config |
| `backend/app/main.py` | FastAPI app with CORS, router includes | No changes needed |
| `backend/app/models/__init__.py` | SQLAlchemy ORM models | May need migration if DB persistence added |
| `backend/app/db/session.py` | Async SQLAlchemy session factory | For DB operations if needed |
| `backend/app/schemas/__init__.py` | Pydantic response models (ApiResponse, ErrorDetail) | Used for consistent API responses |
| `docker-compose.yml` | Multi-container Docker setup (postgres, redis, backend, frontend) | No changes needed |

## Target Project: 实习任务拆解器 (Intern Task Decomposer)

### Purpose
A DeepSeek-powered local AI tool that takes a vague development task and decomposes it into a structured task card that a Coding Agent can execute.

### Tech Stack
- **Frontend**: Single `index.html` — pure HTML/CSS/JavaScript (no framework, no build step)
- **Backend**: Python FastAPI + Pydantic + httpx
- **Model**: DeepSeek Chat Completions API (non-streaming, JSON mode)
- **Secret Storage**: Windows DPAPI encryption (`.local/deepseek_api_key.dpapi`)
- **Persistence**: Browser `localStorage` for draft auto-save

### Architecture
- Frontend collects: raw task description, module/context background, task type (feature/bugfix/review/refactor/test), risk hints (checkboxes), model selection
- Frontend sends to `POST /api/analyze-task` on the backend
- Backend loads the saved DeepSeek API key, calls DeepSeek Chat Completions with structured system/user prompts
- DeepSeek returns JSON with fields: goal, context[], constraints[], done_when[], failure_cases[], verification[], missing_questions[], risk_level, non_goals[]
- Backend THEN deterministically generates an `agent_prompt` from the structured fields (not from model), ensuring consistency
- Backend returns TaskAnalysis with all structured fields + agent_prompt
- Frontend renders the task card in sections + the final Coding Agent prompt

### Backend Files

| File | Responsibility |
|---|---|
| `backend/main.py` | FastAPI app, CORS, 3 endpoints: `/api/health`, `/api/settings/api-key` (GET/POST), `/api/analyze-task` (POST) |
| `backend/schemas.py` | Pydantic models: ApiKeyRequest, ApiKeyStatus, AnalyzeTaskRequest, ModelTaskAnalysis, TaskAnalysis, AnalyzeTaskResponse |
| `backend/deepseek_client.py` | System prompt, user prompt builder, `build_agent_prompt()` (deterministic from structured fields), `analyze_with_deepseek()` (httpx call to DeepSeek API) |
| `backend/secret_store.py` | DpapiSecretStore — Windows DPAPI CryptProtectData/CryptUnprotectData, base64-encrypted file storage |
| `requirements.txt` | fastapi, uvicorn, pydantic, httpx |

### Frontend Features (in index.html)
- Top bar: title, description, API Key input + save button + status pill
- Left panel (input): raw task textarea, context textarea, task type dropdown, model dropdown, risk hint checkboxes (5 items)
- Right panel (output): flow ruler (6 stage labels), dynamic task card rendering, error state
- Buttons: Analyze Task, Copy Markdown, Clear, Load Sample
- `localStorage` auto-save/restore for draft (raw_task, context, task_type, model, risk_hints)
- Toast notifications for user feedback
- Responsive layout (grid → stacked at 880px, 390px narrow screen tested)
- Clipboard API with fallback to `execCommand`

### Data Flow
1. User enters raw task + context + selects options
2. Draft auto-saves to `localStorage`
3. Click "分析任务" → POST /api/analyze-task
4. Backend loads encrypted API key → calls DeepSeek → validates JSON → generates agent_prompt → returns
5. Frontend renders structured task card + prompt
6. User can copy Markdown of the full task card + prompt

### Risk Tags (checkbox options)
- data_loss, compatibility, permission, browser_api, external_service

### Task Types
- feature, bugfix, review, refactor, test

### Models
- deepseek-v4-flash, deepseek-v4-pro

### Key Design Decisions (from planning.md)
- Frontend never calls DeepSeek directly
- Backend owns key management, model calls, JSON validation
- `agent_prompt` is DETERMINISTICALLY generated by backend from structured fields (not by the model), to avoid inconsistency
- No streaming, no WebSocket, no database, no accounts

## Constraints to Preserve

- Tool module must subclass `BaseTool` and implement `handle_invoke()`.
- `tool_id` must be unique, `snake_case`.
- Frontend route path must match `tool_id`.
- Do not modify existing tool behavior or registry registration pattern.
- Never hardcode secrets or credentials.
- Follow three-layer architecture: Frontend ↔ Backend Tool Module ↔ External API (DeepSeek).
- API keys should go via environment variables or encrypted storage, not hardcoded.
- The `agent_prompt` must be deterministically generated from structured analysis fields (not by the LLM).

## Project Vocabulary

| Term | Meaning |
|---|---|
| Task Card | Structured output with Goal, Context, Constraints, Done when, Failure cases, Verification, Missing questions, Non-goals, Agent Prompt |
| agent_prompt | Deterministically generated prompt for Coding Agent, built from structured analysis fields |
| DPAPI | Windows Data Protection API — encrypts the DeepSeek API key at rest |
| risk_hints | User-selected risk tags that influence the model's analysis (data_loss, compatibility, etc.) |
| ModelTaskAnalysis | The raw structured JSON from DeepSeek (no agent_prompt) |
| TaskAnalysis | ModelTaskAnalysis + deterministically generated agent_prompt |

## Verified Facts

- Source project is a self-contained local tool: single `index.html` + 4 Python backend files.
- The existing AI Tool Site uses React (Vite + TypeScript) frontend with FastAPI Python backend.
- Existing tool registration pattern: subclass `BaseTool`, register in `registry.py`, add route in `App.tsx`.
- The AI Tool Site already has DeepSeek API integration infrastructure (chat_tool may use it).
- The source project does NOT use a database — but the AI Tool Site has PostgreSQL + SQLAlchemy + Alembic available if needed.
- The source project uses Windows-specific DPAPI for key storage — the AI Tool Site should use env vars (pydantic-settings) instead.
- Frontend auto-discovery: registration in `registry.py` automatically shows tool in the tool grid.

## Source Repository Analysis

- **Backend size**: ~12KB across 4 Python files (main.py, schemas.py, deepseek_client.py, secret_store.py)
- **Frontend size**: Single 688-line HTML file with embedded CSS + JS (~21KB)
- **No test files** beyond the Playwright UI validation script (validate-ui.cjs)
- **No database** — all persistence is localStorage for draft only; API key is DPAPI-encrypted file

## Uncertainties

- `UNVERIFIED` — Whether the DeepSeek API key should be stored in the AI Tool Site's `.env` (global for all tools) or managed per-tool via the frontend (as in the original). The original uses per-session encryption; the AI Tool Site uses shared env vars.
- `UNVERIFIED` — Whether the backend should persist task analysis records (in PostgreSQL) or keep the stateless approach (no DB for this tool).
- `UNVERIFIED` — How the DeepSeek client module should be structured: as a standalone module within the new tool, or as a shared service (since chat_tool may already have DeepSeek integration).
- `UNVERIFIED` — The exact action dispatch pattern for `handle_invoke` (single endpoint with action routing vs. multiple endpoints).

## Raw Target

Port the Intern Task Decomposer (实习任务拆解器) from a standalone local tool into the AI Tool Site as an integrated tool. This includes:
- A backend tool module that calls DeepSeek Chat Completions with structured prompts
- A frontend page matching the original's UI (task input, risk selection, structured output)
- DeepSeek API key management (via env vars or per-session input)
- Deterministic agent_prompt generation matching the original logic

## Coverage and Safety

- Areas inspected: Full source project (all 4 backend files, index.html, planning.md, AGENTS.md, README.md, requirements.txt, run.ps1, validate-ui.cjs), AI Tool Site full backend structure, frontend structure, routing, config, Docker setup.
- Areas not inspected: Existing DeepSeek integration in chat_tool (may need review during planning), existing database migrations (not relevant unless persistence is added).
- Sensitive information intentionally omitted: API keys, credentials, .env files, user data.

## Handoff

### Workflow

- Workflow ID: `WF-20260725-task-decomposer-A3E1`
- State version: `1`
- Completed role: `CLAUDE_CONTEXT_SCOUT`
- Current stage: `SCOUTING`
- Next role: `HUMAN`
- Branch: `agent/wf-20260725-task-decomposer-a3e1`
- HEAD: `27727ae`

### Completed

- Analyzed target project (实习任务拆解器) — full architecture, tech stack, data flow, frontend/backend design.
- Analyzed AI Tool Site — structure, tool registration pattern, routing, config, deployment.
- Identified key architectural differences: standalone FastAPI vs. modular BaseTool; single HTML file vs. React SPA; DPAPI key storage vs. pydantic-settings env vars.
- Created WORKFLOW.md, 10-context.md, and prepared for Intent discussion.

### Files produced or updated

- `.agent-workspace/workflows/WF-20260725-task-decomposer-A3E1/WORKFLOW.md`
- `.agent-workspace/workflows/WF-20260725-task-decomposer-A3E1/10-context.md`

### Validation

- Manual check — workflow files follow templates, no placeholders remain, branch is correct.
- Residual risk: None at this stage.

### Human action

1. Read the intent questions below.
2. Answer each question to clarify product intent.
3. After answers are clear, I will draft `20-intent.md` for confirmation.

### Copy-Paste Prompt for the Next Agent

N/A — Next is Human discussion.

### Expected next output

Human responses to the intent clarification questions.

### Stop conditions

- Human introduces scope beyond porting the Intern Task Decomposer.
- Human requests production code changes before Intent is confirmed.
