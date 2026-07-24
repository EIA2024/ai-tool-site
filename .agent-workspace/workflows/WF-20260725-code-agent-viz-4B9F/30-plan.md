---
workflow_id: WF-20260725-code-agent-viz-4B9F
status: APPROVED
author_role: CODEX_PLANNING
based_on_commit: f7d7288
human_approval: YES
approved_at_utc: 2026-07-25T13:10:00Z
approved_state_version: 4
approved_head_commit: f7d7288
---

# Implementation Plan

## Goal and Acceptance Mapping

| Acceptance criterion | Plan task |
|---|---|
| AC-1, AC-2, AC-14 | T-3, T-6 |
| AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-20 | T-4, T-5 |
| AC-9, AC-17, AC-19 | T-1, T-2, T-3 |
| AC-10, AC-11, AC-12, AC-13 | T-2, T-4, T-5 |
| AC-15 | T-4, T-5, T-6 |
| AC-16, AC-18 | T-1, T-2, T-3 |

## Verified Repository Findings

- Context freshness verified on 2026-07-24: `HEAD` remains `f7d7288`, and `git diff --name-only f7d7288 HEAD -- . ':(exclude).agent-workspace'` returned no product-file changes.
- `backend/app/models/__init__.py` is the single ORM model file and uses string UUID primary keys with `datetime.utcnow` timestamps.
- `backend/alembic/versions/001_initial_schema.py` is a hand-written migration, so the new table should follow the same explicit migration style.
- `backend/app/api/routes/tools.py` already exposes the generic `POST /api/tools/{tool_id}/invoke` dispatch, so CRUD actions can stay inside the tool module without adding new backend routes.
- `backend/app/tools/registry.py` uses explicit imports and `tool_registry.register(...)`; tool visibility depends on registration, not directory scanning.
- `frontend/src/pages/ToolList.tsx` auto-renders any registered tool returned by `/api/tools`, so homepage discovery does not require a manual card entry.
- `frontend/src/lib/api.ts` already provides generic `get` and `post` helpers that are sufficient for the new page.
- `frontend/src/index.css` only contains shared layout and example-tool styling, so the visualizer page will need additive, page-specific classes for the stage graph, detail panels, forms, history, and notices.

## Approach

- Keep the 9-stage workflow definition in the frontend as a typed constant so stage browsing, prompt templates, and summary generation still work when the backend is unavailable.
- Use PostgreSQL only for practice-record persistence. The frontend owns summary generation, clipboard copy, export formatting, and import confirmation so the backend stays a thin CRUD/action layer.
- Perform duplicate detection on the backend via a deterministic `content_hash` built from stage key plus the four record fields. This keeps normal saves and JSON imports on the same deduplication rule.
- Preserve the existing architecture by adding one model, one Alembic migration, one CRUD service, one request-response tool module with `action` dispatch, one frontend page, one route, and one registry registration.
- Do not add a dedicated backend route, navbar link, AI integration, or extra shared abstractions unless execution reveals a direct blocker.

## Ordered Tasks

### T-1 — Add persistence model and migration

- Change paths:
  - `backend/app/models/__init__.py`
  - `backend/alembic/versions/002_add_agent_practice_records.py`
- Change description:
  - Add `AgentPracticeRecord` to the shared model module with UUID string `id`, `stage_key`, `user_input`, `agent_output`, `feedback`, `next_steps`, deterministic `content_hash`, and `created_at`/`updated_at`.
  - Create a matching Alembic migration for `agent_practice_records`, including a uniqueness constraint or unique index on `content_hash` so duplicate imports are enforced at the database layer.
- Validation commands:
  - `cd backend && alembic upgrade head`
  - `cd backend && python -c "from app.models import AgentPracticeRecord; print(AgentPracticeRecord.__tablename__)"`

### T-2 — Add CRUD service for practice records

- Change paths:
  - `backend/app/services/practice_records.py`
- Change description:
  - Create async CRUD helpers for create-or-detect-duplicate, list all records, fetch one record, and delete one record.
  - Centralize content-hash generation and serialization in the service so the tool module stays focused on request validation and response envelopes.
  - Return enough metadata for the frontend to distinguish a newly created record from a duplicate skip during import.
- Validation commands:
  - `cd backend && python -c "from app.services.practice_records import compute_content_hash; print(callable(compute_content_hash))"`
  - Exercise service behavior through the tool-invoke checks in T-3.

### T-3 — Add backend tool module and register it

- Change paths:
  - `backend/app/tools/modules/code_agent_flow_viz.py`
  - `backend/app/tools/registry.py`
- Change description:
  - Add `CodeAgentFlowVizTool(BaseTool)` with `tool_id = "code_agent_flow_viz"` and `mode = "request-response"`.
  - Implement `handle_invoke(payload)` as explicit `action` dispatch for `save_record`, `list_records`, `get_record`, and `delete_record`, using `async_session_factory` plus the new service helpers.
  - Normalize success and error envelopes so validation failures, missing IDs, duplicate saves, and database failures all return structured JSON instead of raising.
  - Register the tool in the existing registry so `/api/tools` and `/api/tools/code_agent_flow_viz/invoke` work without modifying `backend/app/api/routes/tools.py`.
- Validation commands:
  - `cd backend && python -c "from app.main import app; print('OK')"`
  - `cd backend && python -c "from app.tools.registry import tool_registry; print(tool_registry.get_tool('code_agent_flow_viz').name)"`
  - Manual HTTP checks after the backend is running:
    - `curl http://localhost:8000/api/tools`
    - `curl -X POST http://localhost:8000/api/tools/code_agent_flow_viz/invoke -H "Content-Type: application/json" -d "{\"action\":\"list_records\"}"`

### T-4 — Add frontend types and page-local data contract

- Change paths:
  - `frontend/src/types/index.ts`
  - `frontend/src/pages/tools/CodeAgentFlowVizPage.tsx`
- Change description:
  - Extend shared TypeScript types with the record and invoke payload/response shapes needed by the new page.
  - Define the 9-stage workflow dataset in the page file as a typed constant with titles, goals, prompt templates, checklist items, common errors, and completion criteria.
  - Model local UI state for selected stage, editable draft values, saved history, loading flags, import/export status, summary text, and backend error banners.
- Validation commands:
  - `cd frontend && npm run build`

### T-5 — Implement the visualizer page features and styling

- Change paths:
  - `frontend/src/pages/tools/CodeAgentFlowVizPage.tsx`
  - `frontend/src/index.css`
- Change description:
  - Build the tool page with a 9-node workflow navigator, detail panel, four-field practice form, summary generator, clear action, save action, history list, delete action, JSON export, Markdown export, and JSON import with confirmation.
  - Keep the stage explorer usable when the backend is down by rendering stage content from the local stage constant and surfacing persistence failures in a non-blocking error banner.
  - Use backend `list_records` for initial history load and refresh after create, delete, and import. Use backend duplicate metadata to report imported versus skipped counts accurately.
  - Implement clipboard copy with a fallback path if `navigator.clipboard.writeText` is unavailable in the active browser context.
  - Add page-scoped CSS classes for the workflow layout, responsive cards, form controls, record history, and success/error notices without disturbing existing tool pages.
- Validation commands:
  - `cd frontend && npm run build`
  - Manual browser checks:
    - Open `/tools/code_agent_flow_viz` and click all 9 stages.
    - Save a record, reload the page, and confirm the record persists.
    - Export JSON and Markdown, then re-import the JSON and confirm duplicates are skipped.
    - Temporarily stop the backend or block the invoke call and confirm stage navigation still works while persistence actions show a clear error.

### T-6 — Wire the route and verify end-to-end behavior

- Change paths:
  - `frontend/src/App.tsx`
- Change description:
  - Register the page route at `/tools/code_agent_flow_viz`.
  - Rely on existing backend tool registration plus `ToolList` auto-discovery for homepage visibility; no `ToolList` or backend route changes are planned.
- Validation commands:
  - `cd backend && python -c "from app.main import app; print('OK')"`
  - `cd frontend && npm run build`
  - Manual smoke check: homepage shows the new tool card and clicking it routes to `/tools/code_agent_flow_viz`.

## Change Paths

```paths
backend/app/models/__init__.py
backend/alembic/versions/002_add_agent_practice_records.py
backend/app/services/practice_records.py
backend/app/tools/modules/code_agent_flow_viz.py
backend/app/tools/registry.py
frontend/src/types/index.ts
frontend/src/pages/tools/CodeAgentFlowVizPage.tsx
frontend/src/index.css
frontend/src/App.tsx
```

## Tests and Quality Gates

- Context freshness gate already passed against `f7d7288`.
- Backend import and registration:
  - `cd backend && python -c "from app.main import app; print('OK')"`
  - `cd backend && python -c "from app.tools.registry import tool_registry; print(tool_registry.get_tool('code_agent_flow_viz').tool_id)"`
- Migration and database shape:
  - `cd backend && alembic upgrade head`
- Backend static checks:
  - `cd backend && ruff check .`
- Frontend compile check:
  - `cd frontend && npm run build`
- Manual acceptance checks:
  - `/api/tools` includes `code_agent_flow_viz`
  - `/tools/code_agent_flow_viz` renders all 9 stages
  - save/list/get/delete flows work through the invoke endpoint
  - export/import round-trip preserves data and reports skipped duplicates
  - backend failure does not break stage browsing or prompt copying

## Risks and Stop Conditions

- Risk: clipboard write support can vary in non-secure browser contexts. The executor should add a fallback so AC-7 does not depend on a single API path.
- Risk: duplicate detection needs a canonical hash contract. If line-ending normalization or whitespace rules are ambiguous during implementation, stop and align before shipping to avoid false duplicate matches.
- Risk: the frontend page is larger than the existing examples. Keep the implementation page-local and additive; if the UI starts demanding shared abstractions, stop and justify them before expanding scope.
- Stop if any product file outside `.agent-workspace/` changes after `f7d7288` before plan approval, because `10-context.md` would become stale under the workflow protocol.
- Stop if the executor discovers the generic invoke endpoint cannot support one of the required CRUD flows without changing confirmed Intent or widening backend API scope.

## Approval

- Plan status: `APPROVED`
- Approved by: `HUMAN` (in conversation)
- Approved at: `2026-07-25T13:10:00Z`
- Approved HEAD: `f7d7288`
- Next role: `CLAUDE_EXECUTION`

## Handoff

### Workflow

- Workflow ID: `WF-20260725-code-agent-viz-4B9F`
- State version: `4`
- Completed role: `CODEX_PLANNING`
- Current stage: `CLAUDE_EXECUTION`
- Next role: `CLAUDE_EXECUTION`
- Branch: `agent/wf-20260725-code-agent-viz-4b9f`
- HEAD: `f7d7288`

### Completed

- Human approved the Implementation Plan.

### Files produced or updated

- `.agent-workspace/workflows/WF-20260725-code-agent-viz-4B9F/30-plan.md`
- `.agent-workspace/workflows/WF-20260725-code-agent-viz-4B9F/WORKFLOW.md`

### Validation

- `python .agent-workspace/validators/validate_workflow.py --workflow WF-20260725-code-agent-viz-4B9F` — `PASS`
- Residual risk: Clipboard fallback and duplicate-hash canonicalization need execution-time verification.

### Human action

- None. The Executor will read the confirmed Intent and approved Plan and start implementing.

### Copy-Paste Prompt for the Next Agent

```text
WORKFLOW_ID: WF-20260725-code-agent-viz-4B9F
EXPECTED_STATE_VERSION: 4
ROLE: CLAUDE_EXECUTION
WORKFLOW_PATH: .agent-workspace/workflows/WF-20260725-code-agent-viz-4B9F

Read:
- WORKFLOW.md
- 10-context.md
- 20-intent.md
- 30-plan.md
- .agent-workspace/protocol/WORKFLOW_PROTOCOL.md
- .agent-workspace/protocol/HANDOFF_TEMPLATE.md
- .agent-workspace/protocol/CLAUDE_RULES.md
- docs/ai-tool-development-handbook.md
- AGENTS.md
- backend/app/tools/base.py
- backend/app/tools/registry.py
- backend/app/tools/modules/blank_tool.py
- backend/app/models/__init__.py
- backend/app/db/session.py
- backend/app/services/chat_history.py
- backend/app/api/routes/tools.py
- frontend/src/App.tsx
- frontend/src/pages/tools/BlankToolPage.tsx
- frontend/src/types/index.ts
- frontend/src/lib/api.ts
- frontend/src/index.css

Do:

Follow the approved 30-plan.md exactly. Implement all 6 tasks in order:

T-1 — Add AgentPracticeRecord model and Alembic migration
T-2 — Add CRUD service module
T-3 — Add backend tool module with action dispatch and register
T-4 — Add frontend types and 9-stage constant dataset
T-5 — Implement full frontend visualizer page and styling
T-6 — Wire route in App.tsx

Key constraints:
- tool_id = "code_agent_flow_viz", mode = "request-response"
- All CRUD via POST /api/tools/{tool_id}/invoke with action field
- content_hash for duplicate detection
- Stage navigation works offline (backed by frontend constant)
- No new backend routes, no new dependencies, no new DB tables beyond the one migration
- Do not modify existing tools or patterns

After all tasks:
- Write 40-execution.md with results
- Update WORKFLOW.md to CLAUDE_REVIEW
- Run the Validator
- Provide Review Prompt for a new Claude session

Write:
- 40-execution.md
- All implementation files (see change paths in 30-plan.md)

Do not:
- redefine Intent
- modify code outside allowed change paths
- perform the final Review in the same session
- read sibling Workflow artifacts

Before finishing:
- update WORKFLOW.md and 40-execution.md;
- run the Validator yourself;
- create the next Handoff with this same structure.
```

### Expected next output

- Implemented code changes on branch `agent/wf-20260725-code-agent-viz-4b9f`.
- `40-execution.md` with task results, commits, and validation evidence.
- WORKFLOW.md updated to CLAUDE_REVIEW with candidate HEAD.

### Stop conditions

- Intent redefinition beyond approved scope.
- Template placeholders remain in artifacts.
- Executor attempts Review in the same session.
- Validator fails after implementation.
