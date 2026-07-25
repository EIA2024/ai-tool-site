---
workflow_id: WF-20260725-task-decomposer-A3E1
status: APPROVED
author_role: CODEX_PLANNING
based_on_context_commit: 27727ae
based_on_intent_commit: 27727ae
planned_at_utc: 2026-07-25T00:09:23Z
human_approval: YES
approved_at_utc: 2026-07-25T00:41:11Z
approved_state_version: 4
approved_head_commit: 27727aedb365ea64ea8dce1677cbb1dbd9eb24bd
---

# Plan

## Status

- Plan status: `APPROVED`
- Context freshness: verified against `27727ae`; no product-file changes were detected before planning.
- Scope guard: this plan adds a new tool and its dedicated persistence path without modifying existing tool behavior.

## Acceptance-to-Task Mapping

| Acceptance criteria | Planned work |
|---|---|
| AC-1, AC-2, AC-17 | Add a new backend tool module with `tool_id = "task_decomposer"`, register it in `backend/app/tools/registry.py`, and add the frontend route in `frontend/src/App.tsx`. |
| AC-3, AC-4, AC-8, AC-9, AC-10, AC-15, AC-16 | Build `frontend/src/pages/tools/TaskDecomposerPage.tsx` with the original input controls, sample loader, clear flow, toast feedback, draft persistence in `localStorage`, and a history panel that supports browsing by date and task type. |
| AC-5, AC-6, AC-14 | Implement a self-contained DeepSeek client plus backend action handling for `analyze_task`, including prompt construction, JSON validation, deterministic `agent_prompt` generation, and explicit error mapping. |
| AC-7 | Generate a Markdown representation of the task card on the frontend and copy it with `navigator.clipboard` plus a textarea fallback. |
| AC-11, AC-12, AC-13 | Add a PostgreSQL-backed `task_analysis_history` model, Alembic migration, CRUD service, and tool actions for `list_history`, `get_history`, and `delete_history`. |
| AC-18, AC-19, AC-20 | Validate with backend tests plus migration checks, then run frontend build/lint and smoke-check that existing tools still register and render unchanged. |

## Verified Repository Findings

- `backend/app/tools/base.py` defines a minimal `BaseTool` contract, so all request branching must stay inside the new tool's `handle_invoke()`.
- `backend/app/api/routes/tools.py` already exposes generic `GET /api/tools` and `POST /api/tools/{tool_id}/invoke`, so no route expansion is required for this feature.
- `backend/app/tools/registry.py` uses explicit singleton registration; adding the new tool is a one-line registry change.
- `backend/app/models/__init__.py`, `backend/app/services/practice_records.py`, and `backend/app/tools/modules/code_agent_flow_viz.py` establish the existing persistence pattern: model + service helpers + thin tool action router.
- `backend/app/core/config.py` does not currently expose a `DEEPSEEK_API_KEY` setting, so dual-mode API-key handling needs one config addition plus request-time fallback logic.
- `backend/alembic/versions/002_add_agent_practice_records.py` shows the migration style to follow: sequential numeric revision IDs, explicit `upgrade()` / `downgrade()`, and table/index creation by hand.
- `frontend/src/ToolList.tsx` auto-discovers tools from `/api/tools`, so no homepage code changes are needed beyond backend registration.
- `frontend/src/index.css` is globally dark-themed, which means the paper-like Task Decomposer UI should be implemented with scoped classes so the warm-toned aesthetic does not regress other pages.
- The frontend currently has build/lint scripts but no test runner, so automated coverage should focus on backend pytest while frontend verification stays build-based plus manual responsive checks.

## Implementation Approach

### Backend

1. Add `deepseek_api_key` to `backend/app/core/config.py` so the tool can prefer `.env` configuration without introducing a shared refactor.
2. Extend `backend/app/models/__init__.py` with a new `TaskAnalysisHistory` ORM model that stores:
   - request inputs needed for history preview and filtering: `raw_task`, `context`, `task_type`, `model_name`
   - selected `risk_hints`
   - `risk_level` for quick badge rendering
   - full structured analysis payload, including deterministic `agent_prompt`, in a JSON column
   - timestamps for sorting
3. Add `backend/alembic/versions/003_add_task_analysis_history.py` to create the history table and indexes for `created_at` and `task_type`.
4. Add `backend/app/services/task_decomposer_history.py` to keep CRUD queries out of the tool module while matching the existing `practice_records.py` pattern.
5. Add `backend/app/tools/modules/task_decomposer_client.py` as the self-contained DeepSeek integration layer. It should own:
   - request/response schemas local to the tool
   - system prompt and user prompt builders
   - strict JSON parsing and validation
   - deterministic `agent_prompt` generation from structured fields only
   - API-key resolution order: request `session_api_key` fallback only when `settings.deepseek_api_key` is empty
6. Add `backend/app/tools/modules/task_decomposer.py` as the thin action router. `handle_invoke()` should support only:
   - `analyze_task`
   - `list_history`
   - `get_history`
   - `delete_history`
7. Preserve the existing generic tool route and keep all new behavior isolated to the new tool, service, model, and migration files.

### Frontend

1. Add `frontend/src/pages/tools/TaskDecomposerPage.tsx` with three page regions:
   - top bar: title, short description, API-key field, and mode/status pill
   - input panel: raw task, context, task type, model, risk hints, and action buttons
   - output/history side: flow ruler, task card sections, and persistent history list
2. Add new Task Decomposer types to `frontend/src/types/index.ts` for:
   - request payloads
   - structured analysis payload
   - history list/detail payloads
3. Keep `frontend/src/lib/api.ts` unchanged unless execution reveals a concrete typing gap; existing `get()` / `post()` helpers are already sufficient for the planned requests.
4. Update `frontend/src/App.tsx` with a route for `/tools/task_decomposer`.
5. Extend `frontend/src/index.css` with scoped Task Decomposer styles only. The new styles should provide the warm paper-like look, stacked mobile layout, and the 390px overflow guard without changing existing tool page styling.

### API Key Dual Mode

- Backend rule: resolve API key as `.env` first, then request-scoped `session_api_key`, and fail with a clear validation error if both are absent.
- Frontend rule: never persist the API key to `localStorage` or PostgreSQL. Keep it in component state only.
- Status pill behavior: show mode, not secret state.
  - Empty field: “Using server key if configured”
  - Non-empty field: “Using session key”
- No extra backend action is needed for key-status probing, which keeps `handle_invoke()` aligned with the approved four-action scope.

### History and Draft Behavior

- `localStorage` remains responsible only for the in-progress draft (`raw_task`, `context`, `task_type`, `model`, `risk_hints`).
- PostgreSQL history stores only successful analyses.
- The history list should fetch on mount, support task-type filtering and newest-first ordering, and allow selecting an item to repopulate the output panel without overwriting the current draft.
- Deletion should remove the record from PostgreSQL and optimistically update the local list after success.

## Change Paths

```paths
backend/alembic/versions/003_add_task_analysis_history.py
backend/app/core/config.py
backend/app/models/__init__.py
backend/app/services/task_decomposer_history.py
backend/app/tools/modules/task_decomposer.py
backend/app/tools/modules/task_decomposer_client.py
backend/app/tools/registry.py
backend/tests/services/test_task_decomposer_history.py
backend/tests/tools/test_task_decomposer_tool.py
frontend/src/App.tsx
frontend/src/index.css
frontend/src/pages/tools/TaskDecomposerPage.tsx
frontend/src/types/index.ts
```

## Ordered Tasks

1. Create the backend persistence layer.
   Verify: the ORM model imports cleanly, the migration upgrades and downgrades on a disposable database, and the history service supports create/list/get/delete semantics.
2. Implement the DeepSeek client and deterministic prompt builder.
   Verify: unit tests cover prompt building, API-key resolution, invalid JSON handling, and schema-validation failures without hitting the live API.
3. Implement the `task_decomposer` tool module and register it.
   Verify: backend tests cover `analyze_task`, `list_history`, `get_history`, `delete_history`, unknown-action handling, and `/api/tools` registration visibility.
4. Build the React page and typed payloads.
   Verify: manual smoke checks cover sample loading, clear/reset, draft restore, copy-to-Markdown, history selection, and delete flows.
5. Apply scoped styling for the paper-like UI.
   Verify: the page remains readable at desktop width, stacks cleanly near 880px, and has no horizontal overflow at 390px.
6. Run the final quality gates without touching existing tools.
   Verify: backend tests pass, frontend build/lint pass, migration commands succeed, and existing tools still appear in `/api/tools` and retain their routes.

## Tests and Quality Gates

### Automated

- `cd backend && pytest`
- `cd backend && alembic upgrade head`
- `cd backend && alembic downgrade -1`
- `cd backend && alembic upgrade head`
- `cd frontend && npm run build`
- `cd frontend && npm run lint`

### Planned backend test coverage

- `backend/tests/services/test_task_decomposer_history.py`
  - create history row with JSON analysis payload
  - list rows newest-first
  - fetch one row by id
  - delete row and report not-found correctly
- `backend/tests/tools/test_task_decomposer_tool.py`
  - reject missing `action`
  - reject empty `raw_task`
  - prefer `.env` key over session key
  - use session key when `.env` key is empty
  - surface DeepSeek transport/auth/schema errors clearly
  - persist successful analyses only
  - return history list/detail/delete payloads in frontend-ready shapes

### Manual checks

- Open `/tools/task_decomposer` and confirm the tool appears in the homepage grid.
- Resize to roughly 880px and 390px widths and confirm stacking/no overflow.
- Verify `localStorage` draft restore after refresh.
- Verify history survives refresh because it is loaded from PostgreSQL.
- Verify leaving the API-key field blank still works when `.env` is configured.
- Verify entering a session key works when `.env` is unset.
- Verify the current draft is preserved after backend or DeepSeek failures.

## Risks and Stop Conditions

- Stop if execution discovers product-file drift after `27727ae`; the context will need to be refreshed before implementation proceeds.
- Stop if the source project's deterministic `agent_prompt` behavior cannot be reproduced without widening scope; clarify the exact mismatch before coding.
- Stop if the existing database environment cannot run migrations safely; resolve environment readiness before touching application code.
- Stop if implementation would require changing existing tools, generic routes, or shared architecture beyond the approved Task Decomposer scope.
- Risk: the warm paper-like page could accidentally leak styles into the global dark theme. Mitigation: keep all new CSS under Task Decomposer-specific class names.
- Risk: storing too little history metadata will make list filtering awkward. Mitigation: persist both scalar preview fields and the full structured analysis JSON.

## Handoff

### Workflow

- Workflow ID: `WF-20260725-task-decomposer-A3E1`
- State version: `5`
- Completed role: `HUMAN`
- Current stage: `CLAUDE_EXECUTION`
- Next role: `CLAUDE_EXECUTION`
- Branch: `agent/wf-20260725-task-decomposer-a3e1`
- HEAD: `27727aedb365ea64ea8dce1677cbb1dbd9eb24bd`

### Completed

- Verified context freshness against commit `27727ae`.
- Inspected the authorized backend/frontend surfaces and the existing persistence/migration patterns.
- Wrote a detailed implementation plan for the Task Decomposer tool, including exact change paths, ordered tasks, tests, risks, and scope guards.
- Human explicitly approved the plan, so the Workflow is ready to enter execution.

### Files produced or updated

- `.agent-workspace/workflows/WF-20260725-task-decomposer-A3E1/30-plan.md`
- `.agent-workspace/workflows/WF-20260725-task-decomposer-A3E1/WORKFLOW.md`

### Validation

- `python .agent-workspace/validators/validate_workflow.py --workflow WF-20260725-task-decomposer-A3E1` — `PASS`
- Residual risk: Executor must stop if repository reality contradicts the approved plan or if product files drift beyond the scoped paths.

### Human action

1. Open a fresh Claude execution session.
2. Paste the exact executor prompt below.

### Copy-Paste Prompt for the Next Agent

```text
WORKFLOW_ID: WF-20260725-task-decomposer-A3E1
EXPECTED_STATE_VERSION: 5
ROLE: CLAUDE_EXECUTION
WORKFLOW_PATH: .agent-workspace/workflows/WF-20260725-task-decomposer-A3E1

Read:
- .agent-workspace/protocol/WORKFLOW_PROTOCOL.md
- .agent-workspace/protocol/HANDOFF_TEMPLATE.md
- .agent-workspace/protocol/CODEX_RULES.md
- AGENTS.md
- .agent-workspace/workflows/WF-20260725-task-decomposer-A3E1/WORKFLOW.md
- .agent-workspace/workflows/WF-20260725-task-decomposer-A3E1/10-context.md
- .agent-workspace/workflows/WF-20260725-task-decomposer-A3E1/20-intent.md
- .agent-workspace/workflows/WF-20260725-task-decomposer-A3E1/30-plan.md

Do:
- Implement the approved Task Decomposer plan exactly as written in 30-plan.md.
- Restrict production changes to these planned paths only:
  - backend/alembic/versions/003_add_task_analysis_history.py
  - backend/app/core/config.py
  - backend/app/models/__init__.py
  - backend/app/services/task_decomposer_history.py
  - backend/app/tools/modules/task_decomposer.py
  - backend/app/tools/modules/task_decomposer_client.py
  - backend/app/tools/registry.py
  - backend/tests/services/test_task_decomposer_history.py
  - backend/tests/tools/test_task_decomposer_tool.py
  - frontend/src/App.tsx
  - frontend/src/index.css
  - frontend/src/pages/tools/TaskDecomposerPage.tsx
  - frontend/src/types/index.ts
- Follow the ordered tasks, tests, quality gates, and stop conditions in 30-plan.md.
- Create or update 40-execution.md with implementation evidence, commands run, results, and residual risks.

Write:
- .agent-workspace/workflows/WF-20260725-task-decomposer-A3E1/40-execution.md

Do not:
- read sibling Workflow artifacts;
- change files outside the approved scope unless repository reality forces a stop and replan;
- rewrite confirmed Intent or approved Plan;
- perform the final Review;
- rely only on previous chat memory.

Before finishing:
- update WORKFLOW.md;
- run the Validator yourself;
- create the next Handoff with this same structure.
```

### Expected next output

- Implemented code and `.agent-workspace/workflows/WF-20260725-task-decomposer-A3E1/40-execution.md` prepared for independent review.

### Stop conditions

- Repository reality invalidates the approved plan or requires scope expansion.
- Context becomes stale due to product-file changes outside `.agent-workspace/`.
- Execution would require modifying existing tools beyond the approved integration points.
