---
workflow_id: WF-20260725-code-agent-viz-4B9F
status: DRAFT
based_on_commit: f7d7288
author_role: CLAUDE_CONTEXT_SCOUT
---

# Project Context

## Project Summary

- **Purpose**: AI Tool Site — a web application that hosts a collection of AI-powered tools. Users navigate a tool list, select a tool, and interact with it via REST API or WebSocket.
- **Primary users**: Developers practicing prompt-crafting and AI agent interaction workflows.
- **Main user flow**: User opens homepage → sees tool grid → selects a tool → interacts with the tool (request-response or realtime chat) → sees results.

## Relevant Structure

| Path or component | Responsibility | Relevance |
|---|---|---|
| `backend/app/tools/base.py` | BaseTool ABC — contract for all tool modules | Must subclass for new tool |
| `backend/app/tools/registry.py` | ToolRegistry — singleton that registers and lists tools | Must register new tool here |
| `backend/app/tools/modules/` | Directory for tool module implementations | New tool module goes here |
| `backend/app/api/routes/tools.py` | REST endpoints: GET /api/tools, GET /api/tools/{id}, POST /api/tools/{id}/invoke | Auto-handles registered tools |
| `frontend/src/pages/tools/` | Frontend page implementations for each tool | New tool page goes here |
| `frontend/src/App.tsx` | Route definitions | Must add route for new tool |
| `frontend/src/pages/ToolList.tsx` | Dynamic tool list (fetches from GET /api/tools) | Auto-discovers registered tools |
| `frontend/src/components/layout/NavBar.tsx` | Navigation bar with tool links | May add link for new tool |
| `frontend/src/lib/api.ts` | HTTP client (`get`/`post` helpers) | Used by frontend tool pages |
| `frontend/src/types/index.ts` | TypeScript type definitions (ToolMeta, ApiResponse) | Type definitions for tools |
| `frontend/src/index.css` | Global styles with dark theme | Tool pages use existing CSS classes |
| `docs/ai-tool-development-handbook.md` | Handbook with step-by-step guide for adding tools | Must follow conventions documented here |

## Current Relevant Behavior

- Tool discovery is automatic: registering a tool in `registry.py` makes it visible at `/api/tools` and on the homepage.
- Two tool modes exist: `request-response` (REST POST) and `realtime` (WebSocket).
- Frontend route path must match `tool_id` (underscore-separated).
- Existing tools: `blank_tool` (request-response), `chat_tool` (realtime).
- No database models are required unless the tool needs persistence.
- The project has a full Docker setup and can also run with local Node.js/Python dev servers.

## Constraints to Preserve

- Tool module must subclass `BaseTool` and implement `handle_invoke()`.
- `tool_id` must be unique, `snake_case`.
- Frontend route path must match `tool_id`.
- Do not modify existing tool behavior or registry registration pattern.
- AI API keys go in `config.py` via pydantic-settings `.env`.
- Follow the three-layer architecture: Frontend ↔ Backend Tool Module ↔ Database (if needed).
- Never hardcode secrets or credentials.

## Project Vocabulary

| Term | Meaning |
|---|---|
| BaseTool | Abstract base class for all tool modules (tool_id, name, description, mode, handle_invoke) |
| ToolRegistry | Singleton that holds registered tool instances, provides list/get |
| request-response | Synchronous REST mode — one POST request returns one response |
| realtime | WebSocket mode — bidirectional streaming communication |
| tool_id | Unique snake_case identifier used in URLs and routing |

## Verified Facts

- The tool registry is the central hub; registration alone makes a tool visible in the frontend list.
- POST endpoint auto-routes to any registered tool's `handle_invoke`.
- Frontend uses a dynamic tool grid fetched from API — no hardcoded tool list.
- Both Docker and non-Docker dev workflows exist.

## Source Repository: EIA2024/code-agent-flow-visualizer

- **Purpose**: A local HTML MVP for practicing "vibe coding" with a Code Agent workflow visualizer. Helps users break down a Coding Agent collaboration session into clear stages and record inputs/outputs/feedback/improvements.
- **Tech**: Single `index.html` file (HTML/CSS/JS + localStorage). No dependencies, no build step.
- **Features**: 9 stages (clickable nodes), stage detail panels (goals, prompt templates, replaceable variables, checklists, common errors, completion criteria), practice record form (4 input fields), structured summary generation, copy-prompt button, clear/reset, localStorage persistence, export JSON/Markdown, import JSON with dedup.
- **Version**: MVP — pure frontend, local-only, no backend, no AI API, no accounts.

## Uncertainties

- `RESOLVED` — Database persistence is feasible and adopted: PostgreSQL via existing SQLAlchemy + Alembic stack.
- `UNVERIFIED` — Whether the 9 stages should be server-side defined (registered as a tool) or remain fully client-side. Keeping them as a TypeScript constant for now.
- `UNVERIFIED` — The specific `handle_invoke` action dispatch pattern for CRUD operations.

## Raw Target

Port the Code Agent Flow Visualizer from a single-file HTML MVP into the AI Tool Site as a new tool. The tool should let users visualize a 9-stage coding agent workflow, navigate stages, record practice sessions, and export/import data.

## Coverage and Safety

- Areas inspected: Full project structure, all frontend/backend source files, all docs, handbook.
- Areas not inspected: Existing database schemas (not relevant unless we add persistence), Docker networking details.
- Sensitive information intentionally omitted: API keys, credentials, .env files.

## Handoff

<USE .agent-workspace/protocol/HANDOFF_TEMPLATE.md>
