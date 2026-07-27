# Start Here

## What this package gives you

- Claude Code and Codex share one workflow.
- Either agent can execute any State.
- Switching agents is optional, not mandatory.
- Every target gets an independent Branch, Worktree, Run ID, state, and artifacts.
- A Master Integrator handles cross-Workflow merges.
- State 9 happens after final merge, cancellation, or terminal failure.

## Recommended default

Use one agent for a Run unless there is a reason to switch. Switch only at a safe checkpoint.

## Initialize project knowledge

Complete:

```text
.workflow/project/CONTEXT.md
.workflow/project/ARCHITECTURE.md
.workflow/project/CONVENTIONS.md
.workflow/project/COMMANDS.md
```

Only record stable, verified project knowledge.

## Run lifecycle

```text
CREATE
→ S1 Goal
→ S2 Research
→ S3 Specification
→ S4 Planning
→ S5 Implementation
→ S6 Validation
→ S7 Review
→ S8 Candidate Freeze
→ Merge Queue
→ Master Integration
→ merged / cancelled / terminal failure
→ S9 Retro
→ archived
```

## Non-negotiable rules

1. One target equals one Run.
2. One Run equals one branch and one Worktree.
3. The branch determines the Run ID.
4. Only one writing agent may own a Worktree at a time.
5. Takeover occurs only at a checkpoint.
6. Child Runs never merge directly into `main`.
7. Candidate SHA changes invalidate candidate approval, validation, and review.
8. Integration occurs in a separate integration Worktree.
9. Product-private memory is not workflow state.
10. Chat history is not workflow state.
