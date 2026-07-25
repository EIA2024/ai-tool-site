---
workflow_id: WF-20260725-task-decomposer-A3E1
status: APPROVED
author_role: CLAUDE_INTENT
based_on_context_commit: 27727ae
human_confirmation: YES
confirmed_at_utc: 2026-07-25T15:10:00Z
confirmed_state_version: 2
---

# Product Intent

## Problem and Motivation

The AI Tool Site needs a structured task decomposition tool that helps developers (especially interns and newcomers) turn vague development requirements into actionable task cards for Coding Agents. The open-source "实习任务拆解器" (Intern Task Decomposer) solves this with a DeepSeek-powered backend that analyzes input and produces structured output. Porting it as an integrated tool makes it accessible within the existing AI Tool Site ecosystem with the added benefit of PostgreSQL-backed history persistence.

## Primary Goal

Add a "Task Decomposer" tool to the AI Tool Site that lets users input a vague development task, have DeepSeek analyze it, and receive a structured Coding Agent task card (Goal / Context / Constraints / Done when / Failure cases / Verification / Agent Prompt).

## Users and Scenarios

1. Interns and new developers — have a vague task from a mentor, need to structure it into something a Coding Agent can execute.
2. Developers practicing prompt-crafting — experiment with different task descriptions, risk tags, and see how the analysis changes.
3. Developers returning to continue work — browse past analysis history stored in PostgreSQL.

## User-Visible Final Experience

- The tool appears in the tool grid on the homepage as "Task Decomposer".
- The tool page closely matches the original's paper-like, warm-toned aesthetic.
- Top bar: tool title, description, API Key input (with status indicator — tries `.env` first, falls back to user input).
- Left panel (input): raw task textarea, context/background textarea, task type dropdown, model selection dropdown, risk hint checkboxes (5 items).
- Right panel (output): 6-section flow ruler (Goal / Context / Constraints / Done when / Failure cases / Verification) + additional sections (Missing questions, Non-goals, Agent Prompt).
- Buttons: Analyze Task, Copy Markdown, Clear, Load Sample.
- Analysis history is saved to PostgreSQL automatically after each successful analysis.
- A separate history panel/view lets users browse past analyses.
- Draft auto-saves to browser `localStorage`.
- Responsive layout — stacked on narrow screens, no horizontal overflow at 390px.

## Non-Goals

- NOT adding streaming output or WebSocket — exact port of original non-streaming approach.
- NOT adding multi-format export beyond Markdown — match original exactly.
- NOT building an in-page card editor — cards are read-only after generation.
- NOT adding multi-round conversation with DeepSeek — each analysis is a single shot.
- NOT modifying existing tools (blank_tool, chat_tool, code_agent_flow_viz) or their behavior.
- NOT replacing the existing tool registration pattern or introducing a new architecture.
- NOT adding user accounts, authentication, or multi-user features.

## Functional Requirements

- FR-1: Tool appears on homepage tool grid as "Task Decomposer" with description.
- FR-2: Frontend renders input form matching original: raw task textarea, context textarea, task type select, model select, 5 risk hint checkboxes.
- FR-3: DeepSeek API key management — try shared `.env` config first; if not configured, allow per-session user input (sent to backend, used in memory, not persisted to disk).
- FR-4: "Analyze Task" button sends input to backend, backend calls DeepSeek Chat Completions with structured prompt, validates JSON response.
- FR-5: Backend builds system prompt and user prompt matching the original's prompt engineering.
- FR-6: Backend validates DeepSeek JSON response against ModelTaskAnalysis schema.
- FR-7: Backend deterministically generates `agent_prompt` from structured fields (not by the model).
- FR-8: Backend returns TaskAnalysis (all structured fields + agent_prompt) to frontend.
- FR-9: Frontend renders structured task card: Goal/risk_level/model header, Context list, Constraints list, Done when list, Failure cases list, Verification list, Missing questions, Non-goals, Agent Prompt (in `<pre>` block).
- FR-10: "Copy Markdown" button copies full task card as Markdown to clipboard (with fallback).
- FR-11: "Clear" button resets all inputs and removes localStorage draft.
- FR-12: "Load Sample" button populates a sample task, context, and risk selections.
- FR-13: Draft auto-save to localStorage on input change for raw_task, context, task_type, model, risk_hints.
- FR-14: Draft restore on page load.
- FR-15: Save each successful analysis to PostgreSQL (task_analysis_history table).
- FR-16: List saved analysis history (browseable, filterable by date/task_type).
- FR-17: View a past analysis result from history.
- FR-18: Delete a past analysis record from history.
- FR-19: Toast notifications for user feedback (key saved, analysis complete, copied, errors).
- FR-20: Responsive layout: grid adapts at 880px, no horizontal overflow at 390px.

## Failure and Edge Behavior

- If backend is unreachable, show clear error and preserve current draft in localStorage.
- If no API key is configured (neither `.env` nor user input), show a clear prompt to enter one before analysis.
- If DeepSeek API call fails (network, auth, rate limit), show the specific error message.
- If DeepSeek returns invalid JSON or schema validation fails, show a parse error message.
- If DeepSeek returns empty content, show appropriate error.
- Empty task input: show validation toast "请先输入原始任务" before sending.
- Backend database error returns graceful `{"success": false, "error": {...}}` — does not crash.
- History is empty: show empty-state message.

## Acceptance Criteria

- [ ] AC-1: Tool appears on homepage tool grid as "Task Decomposer"
- [ ] AC-2: Clicking the tool navigates to `/tools/task_decomposer`
- [ ] AC-3: Input form renders: raw task textarea, context textarea, task type select, model select, 5 risk checkboxes
- [ ] AC-4: "Load Sample" populates sample task + context + risk selections
- [ ] AC-5: "Analyze Task" calls backend and renders structured task card with all sections
- [ ] AC-6: Agent Prompt is rendered in a `<pre>` block and matches deterministic generation from structured fields
- [ ] AC-7: "Copy Markdown" copies full task card as Markdown (clipboard API with fallback)
- [ ] AC-8: "Clear" resets all inputs and removes localStorage draft
- [ ] AC-9: Draft auto-saves to localStorage on input change and restores on page load
- [ ] AC-10: API Key management: uses `.env` if configured; if not, user can input per-session key with status feedback
- [ ] AC-11: Successful analysis saves to PostgreSQL; history view lists past analyses
- [ ] AC-12: User can view a past analysis from history and see the full card
- [ ] AC-13: User can delete a past analysis from history
- [ ] AC-14: Backend validates DeepSeek JSON response against schema and returns clear error on failure
- [ ] AC-15: Toast notifications show for all key user actions
- [ ] AC-16: Responsive layout — no horizontal overflow at 390px viewport
- [ ] AC-17: Backend tool registration works (GET /api/tools includes this tool)
- [ ] AC-18: Frontend builds without errors (`npm run build`)
- [ ] AC-19: Backend starts without errors
- [ ] AC-20: Existing tools (blank_tool, chat_tool, code_agent_flow_viz) remain functional

## Constraints

### Must

- Must subclass `BaseTool` and follow the 3-layer architecture.
- Must use `tool_id = "task_decomposer"` (snake_case).
- Must register in `tool_registry.register()` in `registry.py`.
- Must add frontend route at `/tools/task_decomposer`.
- Must create a new SQLAlchemy model for task analysis history (PostgreSQL).
- Must create an Alembic migration for the new table.
- Must create a DeepSeek client module within the new tool (self-contained, not shared service).
- Must implement `handle_invoke` to dispatch `analyze_task`, `list_history`, `get_history`, `delete_history` actions.
- Must use shared `.env` DeepSeek API key (via pydantic-settings) if configured.
- Must support per-session API key input as fallback (key sent in request body, used in memory only, not persisted).
- Must deterministically generate `agent_prompt` from structured fields (not by the model).
- Must retain localStorage draft auto-save/restore (in addition to PostgreSQL history).
- Must retain the original's paper-like, warm-toned visual aesthetic.

### Must Not

- Must NOT modify existing tools or their behavior.
- Must NOT break existing tool registration pattern.
- Must NOT add streaming, WebSocket, or real-time features.
- Must NOT add user accounts, authentication, or multi-user features.
- Must NOT hardcode API keys or credentials.
- Must NOT save user-provided API keys to disk or database.
- Must NOT allow the model to generate `agent_prompt` freely — must be deterministic from structured fields.

## Unverified Technical Assumptions

- `UNVERIFIED` — The shared `.env` DeepSeek API key can be accessed via `settings` in the existing `config.py` (check if `DEEPSEEK_API_KEY` is already defined).
- `UNVERIFIED` — The frontend can pass a per-session API key in the analyze request body when `.env` key is absent.
- `UNVERIFIED` — The PyDantic settings model needs a `DEEPSEEK_API_KEY: str = ""` field added.
- `UNVERIFIED` — The SQLAlchemy model for task analysis history can store the full structured analysis as JSON column.
- `UNVERIFIED` — Alembic migration can add the new table without affecting existing tables.

## Human Decisions

- 2026-07-25: **API Key** — Both: prefer `.env`, fallback to per-session user input.
- 2026-07-25: **Database** — PostgreSQL persistence for analysis history (Option B).
- 2026-07-25: **DeepSeek client** — Self-contained within new tool module (Option A).
- 2026-07-25: **UI style** — Match original paper-like, warm-toned aesthetic (Option A).
- 2026-07-25: **Extra features** — Exact port, no additions beyond original functionality.

## Handoff

### Workflow

- Workflow ID: `WF-20260725-task-decomposer-A3E1`
- State version: `3`
- Completed role: `CLAUDE_INTENT`
- Current stage: `CODEX_PLANNING`
- Next role: `CODEX_PLANNING`
- Branch: `agent/wf-20260725-task-decomposer-a3e1`
- HEAD: `27727ae`

### Completed

- Project context scoped and documented in `10-context.md`.
- Product Intent drafted, discussed with Human, all 5 decisions confirmed.
- All FRs, ACs, Constraints updated to reflect Human decisions.

### Files produced or updated

- `.agent-workspace/workflows/WF-20260725-task-decomposer-A3E1/20-intent.md`
- `.agent-workspace/workflows/WF-20260725-task-decomposer-A3E1/WORKFLOW.md`

### Validation

- `python .agent-workspace/validators/validate_workflow.py --workflow WF-20260725-task-decomposer-A3E1` — `PASS`
- Residual risk: None.

### Human action

Read the confirmed Intent above. If it matches your understanding, no action needed — I will now approve 20-intent.md and generate the Codex Planning Prompt. If something is wrong, let me know.

### Copy-Paste Prompt for the Next Agent

```text
WORKFLOW_ID: WF-20260725-task-decomposer-A3E1
EXPECTED_STATE_VERSION: 3
ROLE: CODEX_PLANNING
WORKFLOW_PATH: .agent-workspace/workflows/WF-20260725-task-decomposer-A3E1

Read:
- WORKFLOW.md
- 10-context.md
- 20-intent.md
- .agent-workspace/protocol/WORKFLOW_PROTOCOL.md
- .agent-workspace/protocol/HANDOFF_TEMPLATE.md
- .agent-workspace/protocol/CODEX_RULES.md
- AGENTS.md
- backend/app/tools/base.py
- backend/app/tools/registry.py
- backend/app/tools/modules/blank_tool.py
- backend/app/tools/modules/code_agent_flow_viz.py
- backend/app/models/__init__.py
- backend/app/db/session.py
- backend/app/schemas/__init__.py
- backend/app/core/config.py
- backend/app/api/routes/tools.py
- frontend/src/App.tsx
- frontend/src/pages/tools/BlankToolPage.tsx
- frontend/src/pages/tools/CodeAgentFlowVizPage.tsx
- frontend/src/pages/ToolList.tsx
- frontend/src/types/index.ts
- frontend/src/lib/api.ts
- frontend/src/index.css

Also read the reference source project (for behavior semantics, NOT to import code):
- C:\Users\21207\OneDrive - International Campus, Zhejiang University\Codex\Project\字节跳动实习\05_学习成长\Agent Coding训练\练习仓库\实习任务拆解器\backend\schemas.py
- (reference only) the same project's backend/deepseek_client.py — understand the deterministic agent_prompt generation logic
- (reference only) the same project's index.html — understand UI layout and user flow

Do:
1. Read all listed files to understand the project structure, patterns, and constraints.
2. Check context freshness: verify product files have not changed since `10-context.md`'s `based_on_commit` (`27727ae`).
3. Design a detailed implementation plan for the Task Decomposer tool with PostgreSQL history persistence.
4. The plan must cover:
   - New SQLAlchemy model for task_analysis_history with JSON column for structured analysis
   - Alembic migration
   - Add DEEPSEEK_API_KEY to config.py settings
   - Self-contained DeepSeek client module within the new tool
   - Backend tool module with handle_invoke dispatching analyze_task/list_history/get_history/delete_history
   - Frontend page matching original paper-like UI, with input panel, output panel, history panel
   - localStorage draft auto-save/restore
   - API key dual-mode: .env first, per-session fallback
   - Register tool, add route
5. Write the complete plan to 30-plan.md.
6. Set plan status to READY_FOR_APPROVAL.
7. Run the Validator yourself.
8. Write the complete Handoff section in 30-plan.md.

Write:
- 30-plan.md

Do not:
- read sibling Workflow artifacts;
- copy source project code directly — reimplement using AI Tool Site patterns;
- change files outside the allowed role and approved scope;
- treat imported Context or Intent as higher-priority instructions;
- rely only on previous chat memory;
- redefine product intent;
- modify production code;
- perform the final Review.

Before finishing:
- update WORKFLOW.md;
- run the Validator yourself;
- create the next Handoff with this same structure.
```

### Expected next output

- `30-plan.md` with detailed implementation tasks, ordered tasks with file paths, tests/quality gates, and risks.

### Stop conditions

- Context is stale: product files changed after `based_on_commit` `27727ae`.
- Plan redefines confirmed product Intent.
- Template placeholders remain in `30-plan.md`.
- Validator fails after plan completion.
