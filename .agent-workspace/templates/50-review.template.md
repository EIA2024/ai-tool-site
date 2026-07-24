---
workflow_id: <WORKFLOW_ID>
status: NOT_REVIEWED
author_role: CLAUDE_REVIEW
candidate_head: <COMMIT>
review_session: FRESH
---

# Independent Review

## Reviewer Independence

- [ ] Review ran in a new Claude session.
- [ ] Reviewer did not rely on Executor chat memory.
- [ ] Reviewer did not modify production code.

## Inputs Reviewed

- [ ] Confirmed Product Intent
- [ ] Approved Plan
- [ ] Execution evidence
- [ ] Actual diff and commits
- [ ] Tests and quality gates
- [ ] Workflow isolation

## Acceptance Review

| Criterion | Implementation evidence | Test evidence | Result |
|---|---|---|---|

## Plan Task Review

| Task | Result | Notes |
|---|---|---|

## Findings

Use stable IDs such as `F-001`.

### Critical

- None.

### Major

- None.

### Minor

- None.

## Decision

- Review status: `ACCEPT | REMEDIATE | BLOCK`
- Residual risk:
- Merge recommendation:

## Handoff

<USE .agent-workspace/protocol/HANDOFF_TEMPLATE.md>
