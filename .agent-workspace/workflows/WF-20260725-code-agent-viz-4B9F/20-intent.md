---
workflow_id: WF-20260725-code-agent-viz-4B9F
status: APPROVED
author_role: CLAUDE_INTENT
based_on_context_commit: f7d7288
human_confirmation: YES
confirmed_at_utc: 2026-07-25T13:00:00Z
confirmed_state_version: 2
---

# Product Intent

## Problem and Motivation

The AI Tool Site needs a visual aid for developers who practice "vibe coding" — collaborating with Coding Agents (Claude Code, Codex, etc.). The Code Agent Flow Visualizer from EIA2024/code-agent-flow-visualizer helps users learn and practice the 9-stage coding agent workflow. Porting it as an integrated tool makes it accessible within the existing AI Tool Site ecosystem.

## Primary Goal

Add a "Code Agent Flow Visualizer" tool to the AI Tool Site that lets users explore the 9 stages of a coding agent collaboration, practice filling in records per stage, and export/import their practice data.

## Users and Scenarios

1. Developers new to coding-agent workflows — explore the 9 stages, understand what each stage requires, read prompt templates and checklists.
2. Developers practicing prompt-crafting — select a stage, fill in their input, record agent output, note feedback and improvements, generate a structured summary, save to database.
3. Users returning to continue practice — records persist in PostgreSQL across sessions and devices; they can export as JSON/Markdown backup and import later.

## User-Visible Final Experience

- The tool appears in the tool grid on the homepage as "Code Agent Flow Visualizer".
- The tool page shows 9 clickable stage nodes in a workflow layout.
- Clicking a node displays that stage's details: goals, prompt template with variables, checklist, common mistakes, completion criteria.
- Each stage has a practice record form (4 fields: User Input, Agent Output, Feedback, Next Steps).
- User can generate a structured summary of the current record.
- User can copy the prompt template to clipboard.
- User can clear the current record.
- User can export all practice history as JSON or Markdown.
- User can import a JSON backup with confirmation dialog and duplicate detection.
- All practice records persist in PostgreSQL and are available across page refreshes.

## Non-Goals

- NOT building a real AI API integration (the original is pure frontend).
- NOT implementing WebSocket streaming or real-time AI chat.
- NOT adding user accounts, authentication, or multi-user features.
- NOT replacing the existing chat_tool or blank_tool.
- NOT implementing the "future upgrade" features listed in the original repo's README (multi-round, multi-project, completion tracking).
- NOT adding Redis caching for this tool's data (PostgreSQL query volume is low).

## Functional Requirements

- FR-1: Display 9 coding agent stages as clickable visual nodes.
- FR-2: Each stage shows: title, goals, prompt template (with replaceable variables), checklist, common errors, completion criteria.
- FR-3: Practice record form with 4 input fields: user_input, agent_output, feedback, next_steps.
- FR-4: "Generate Summary" button produces structured markdown text from current record.
- FR-5: "Copy Prompt" button copies the stage's prompt template to clipboard with feedback.
- FR-6: "Clear Current" resets the record form without affecting saved history.
- FR-7: Save practice records to PostgreSQL via POST `/api/tools/code_agent_flow_viz/invoke` with action `save_record`.
- FR-8: List all saved practice records from PostgreSQL via invoke action `list_records`.
- FR-9: Get a single record by ID via invoke action `get_record`.
- FR-10: Delete a record via invoke action `delete_record`.
- FR-11: Export all history as JSON download (fetched from backend via `list_records`).
- FR-12: Export all history as Markdown download (same data, formatted as .md on frontend).
- FR-13: Import JSON backup with confirmation dialog — frontend parses, sends records via `save_record`, skips duplicates by content hash.
- FR-14: Reject invalid JSON import without corrupting existing records.
- FR-15: Create Alembic migration adding the `agent_practice_records` table.

## Failure and Edge Behavior

- If backend is unreachable or database connection fails, the UI shows a clear error banner but the 9-stage visualization remains usable (stage navigation, prompt templates, copy-prompt all work offline).
- If user imports a file with malformed JSON, show error and preserve existing records.
- Duplicate imports (same content) are detected and skipped via content hash — user sees a count of skipped entries.
- Empty record fields show placeholder guidance rather than blank states.
- If no records exist, history view shows empty-state message; export buttons produce a graceful message.

## Acceptance Criteria

- [ ] AC-1: Tool appears on homepage tool grid as "Code Agent Flow Visualizer"
- [ ] AC-2: Clicking the tool navigates to `/tools/code_agent_flow_viz`
- [ ] AC-3: 9 stage nodes are displayed and clickable — clicking switches the detail panel
- [ ] AC-4: Each stage detail shows: goals, prompt template, checklist, errors, completion criteria
- [ ] AC-5: Practice record form has 4 input fields (user_input, agent_output, feedback, next_steps)
- [ ] AC-6: "Generate Summary" produces structured text with stage name and all 4 field values
- [ ] AC-7: "Copy Prompt" copies stage prompt template to clipboard
- [ ] AC-8: "Clear Current" resets the form fields
- [ ] AC-9: Submit saves record to PostgreSQL; list view retrieves all saved records
- [ ] AC-10: Export JSON downloads a `.json` file with all records (fetched from backend)
- [ ] AC-11: Export Markdown downloads a `.md` file with all records (fetched from backend)
- [ ] AC-12: Import JSON shows confirmation with count; appends new, skips duplicates by content hash
- [ ] AC-13: Invalid JSON import shows error and preserves existing records
- [ ] AC-14: Backend tool registration works (GET /api/tools includes this tool)
- [ ] AC-15: Frontend builds without errors (`npm run build`)
- [ ] AC-16: Backend starts without errors (`python -c "from app.main import app"`)
- [ ] AC-17: `handle_invoke` handles actions `save_record`, `list_records`, `get_record`, `delete_record`
- [ ] AC-18: Alembic migration `agent_practice_records` table created and applied successfully
- [ ] AC-19: Backend DB error returns graceful `{"success": false, "error": {...}}` — does not crash
- [ ] AC-20: Stage navigation and prompt templates work even when backend is unreachable

## Constraints

### Must

- Must subclass `BaseTool` and follow the 3-layer architecture.
- Must use `tool_id = "code_agent_flow_viz"` (underscore, snake_case).
- Must register in `tool_registry.register()` in `registry.py`.
- Must add frontend route at `/tools/code_agent_flow_viz`.
- Must create a new SQLAlchemy model `AgentPracticeRecord` in `backend/app/models/__init__.py`.
- Must create an Alembic migration for the new table.
- Must create a CRUD service module `backend/app/services/practice_records.py`.
- Must implement `handle_invoke` to dispatch `save_record`, `list_records`, `get_record`, `delete_record` actions.

### Must Not

- Must NOT add AI API dependencies or API keys.
- Must NOT modify existing tools, models, or registry registration pattern.
- Must NOT require a backend-available AI model — the tool is self-contained frontend logic.
- Must NOT break existing tools (blank_tool, chat_tool) or their tests.
- Must NOT block the UI if the backend is unreachable — stage navigation must work offline.

## Unverified Technical Assumptions

- `UNVERIFIED` — The tool's stage data (9 stages with goals, templates, checklists) can be hardcoded as a TypeScript constant in the frontend.
- `UNVERIFIED` — The backend tool module's `handle_invoke` can dispatch CRUD actions (`save_record`, `list_records`, `get_record`, `delete_record`) using the existing POST `/api/tools/{tool_id}/invoke` endpoint pattern.
- `UNVERIFIED` — The Copy Prompt API (`navigator.clipboard.writeText`) works in the Vite dev environment over HTTP (may require HTTPS or fallback to `execCommand`).
- `UNVERIFIED` — Content-hash based duplicate detection is reliable for import — using SHA-256 of JSON-serialized record fields.
- `UNVERIFIED` — The backend database is reachable in both Docker and non-Docker dev modes — the frontend should handle DB errors gracefully.

## Human Decisions

- Confirmed 2026-07-25: Use PostgreSQL persistence (Option B) instead of localStorage. All FRs, ACs, and Constraints updated to reflect database-backed CRUD.

## Handoff

### Workflow

- Workflow ID: `WF-20260725-code-agent-viz-4B9F`
- State version: `2`
- Completed role: `CLAUDE_INTENT`
- Current stage: `CODEX_PLANNING`
- Next role: `CODEX_PLANNING`
- Branch: `agent/wf-20260725-code-agent-viz-4b9f`
- HEAD: `f7d7288`

### Completed

- Project context scoped and documented in `10-context.md`.
- Product Intent drafted, discussed with Human, accepted.
- Database persistence (PostgreSQL) confirmed as replacement for localStorage.
- All FRs, ACs, Constraints updated to reflect DB-backed CRUD.

### Files produced or updated

- `.agent-workspace/workflows/WF-20260725-code-agent-viz-4B9F/10-context.md`
- `.agent-workspace/workflows/WF-20260725-code-agent-viz-4B9F/20-intent.md`
- `.agent-workspace/workflows/WF-20260725-code-agent-viz-4B9F/WORKFLOW.md`

### Validation

- `python .agent-workspace/validators/validate_workflow.py --workflow WF-20260725-code-agent-viz-4B9F` — `PASS`
- Residual risk: None.

### Human action

- Approve or request changes to the Codex-generated Plan in the Codex conversation.

### Copy-Paste Prompt for the Next Agent

```text
WORKFLOW_ID: WF-20260725-code-agent-viz-4B9F
EXPECTED_STATE_VERSION: 2
ROLE: CODEX_PLANNING
WORKFLOW_PATH: .agent-workspace/workflows/WF-20260725-code-agent-viz-4B9F

Read:
- WORKFLOW.md
- 10-context.md
- 20-intent.md
- .agent-workspace/protocol/WORKFLOW_PROTOCOL.md
- .agent-workspace/protocol/HANDOFF_TEMPLATE.md
- .agent-workspace/protocol/CODEX_RULES.md
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
- frontend/src/pages/tools/ChatToolPage.tsx
- frontend/src/pages/ToolList.tsx
- frontend/src/types/index.ts
- frontend/src/lib/api.ts
- frontend/src/index.css

Do:
1. Read all listed files to understand the project structure, patterns, and constraints.
2. Check context freshness: verify product files have not changed since `10-context.md`'s `based_on_commit` (`f7d7288`).
3. Design a detailed implementation plan for porting the Code Agent Flow Visualizer as a tool with PostgreSQL persistence.
4. The plan must cover:
   - New SQLAlchemy model `AgentPracticeRecord` with Alembic migration
   - CRUD service layer `backend/app/services/practice_records.py`
   - Backend tool module `backend/app/tools/modules/code_agent_flow_viz.py` with `handle_invoke` dispatching `save_record`/`list_records`/`get_record`/`delete_record`
   - Frontend page `frontend/src/pages/tools/CodeAgentFlowVizPage.tsx` with: 9-stage node visualization, detail panels, practice record form, generate summary, copy prompt, clear, save/list/delete via API, export JSON/Markdown, import JSON with dedup
   - Register tool in `registry.py`
   - Add route in `App.tsx`
   - NavBar link (optional)
5. Write the complete plan to `30-plan.md`.
6. Set plan status to `READY_FOR_APPROVAL`.
7. Run the Validator yourself.
8. Write the complete Handoff section in `30-plan.md`.

Write:
- 30-plan.md

Do not:
- read sibling Workflow artifacts;
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

- `30-plan.md` with detailed implementation tasks, acceptance-to-task mapping, ordered tasks with file paths, change paths, tests/quality gates, and risks.

### Stop conditions

- Context is stale: product files changed after `based_on_commit` `f7d7288`.
- Plan redefines confirmed product Intent.
- Template placeholders remain in `30-plan.md`.
- `30-plan.md` contains wildcard paths, absolute paths, or `..` references.
- Validator fails after plan completion.
