---
workflow_id: <WORKFLOW_ID>
title: <TITLE>
status: ACTIVE
stage: SCOUTING
state_version: 1
created_at_utc: <UTC_TIME>
created_by: <HUMAN_OR_AGENT>
base_branch: <BASE_BRANCH>
base_commit: <BASE_COMMIT>
working_branch: agent/<WORKFLOW_ID_LOWER>
current_owner: CLAUDE_CONTEXT_SCOUT
last_updated_utc: <UTC_TIME>
repository_head: <HEAD_COMMIT>
execution_mode: SERIAL
approved_remediation_findings: NONE
depends_on_commit: NONE
---

# Workflow

## Raw Target

<RAW_TARGET>

## Scope Boundary

- This Workflow owns one target.
- Independent targets require new Workflow IDs.
- Execution is serial.

## Human Decisions

- None recorded.

## Blockers

- None.

## History

| State version | Stage | Owner | HEAD | Summary |
|---:|---|---|---|---|
| 1 | SCOUTING | CLAUDE_CONTEXT_SCOUT | `<HEAD_COMMIT>` | Workflow created |
