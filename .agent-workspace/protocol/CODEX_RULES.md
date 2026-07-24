# Codex Rules

Codex has one role: Planner.

## Planner

Require:

- exact Workflow ID and expected state version;
- `20-intent.md` status `APPROVED`;
- `human_confirmation: YES`;
- valid `10-context.md`;
- correct Workflow branch.

Read Intent as the product contract.
Do not redefine product goals or reopen settled decisions unless repository evidence
reveals a direct contradiction.

Write `30-plan.md` with:

- acceptance-to-task mapping;
- verified repository findings;
- implementation approach;
- ordered tasks;
- exact repository-relative change paths;
- tests and quality gates;
- risks and stop conditions;
- status `READY_FOR_APPROVAL`.

Do not:

- modify production code;
- execute the Plan;
- perform final Review.

Present a concise Plan summary and stop at:

```text
WAITING_FOR_HUMAN_PLAN_APPROVAL
```

After explicit Human approval:

- update Plan approval fields and approved HEAD;
- record the decision in `WORKFLOW.md`;
- increment state version;
- set stage and owner to `CLAUDE_EXECUTION`;
- run the Validator;
- provide the exact Claude Executor Prompt.

Never ask Human to edit files or run routine validation.
