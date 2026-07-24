# Claude Code Rules

## Bootstrap, Context, and Intent

When Human starts a target:

1. scan `.agent-workspace/workflows/`;
2. generate one unique immutable Workflow ID;
3. create or switch to `agent/<workflow-id-lowercase>`;
4. create the six Workflow files from the templates;
5. record the raw target in `WORKFLOW.md`;
6. inspect stable project context and target-relevant repository areas;
7. write concise `10-context.md`;
8. discuss product intent with Human using repository facts;
9. ask only questions whose answers materially affect the product result;
10. draft `20-intent.md`;
11. present a concise Intent summary and acceptance criteria;
12. stop at `WAITING_FOR_HUMAN_INTENT_CONFIRMATION`;
13. do not modify production code.

After explicit confirmation, approve `20-intent.md`, record the decision, move to
`CODEX_PLANNING`, validate, and provide the Codex Planning Prompt.

## Executor

Require:

- exact Workflow ID;
- approved `20-intent.md`;
- approved `30-plan.md`;
- correct branch;
- approved starting HEAD matching repository reality.

Then:

- modify only approved paths and necessary adjacent tests;
- do not rewrite Intent or Plan;
- record files, commits, tests, deviations, and residual risk;
- write `40-execution.md`;
- set status `READY_FOR_REVIEW`;
- set stage and owner to `CLAUDE_REVIEW`;
- run the Validator;
- provide an exact Review Prompt for a new Claude session.

The Executor must not perform the Review in the same session.

## Independent Reviewer

Require:

- a fresh Claude session;
- exact Workflow ID and expected state version;
- stage `CLAUDE_REVIEW`;
- approved Intent and Plan;
- completed Execution evidence.

Review actual repository evidence, not only `40-execution.md`.

Check:

- every acceptance criterion;
- every Plan task;
- actual diff and commits;
- tests and quality gates;
- regressions and edge cases;
- scope compliance;
- security and maintainability risks.

Write `50-review.md` with stable Finding IDs and one decision:

```text
ACCEPT
REMEDIATE
BLOCK
```

Do not modify production code.

For `REMEDIATE`, ask Human to select exact Finding IDs.
After selection, record them, move to `REMEDIATION`, validate, and provide the
Claude Remediation Prompt.

For `ACCEPT`, ask Human whether to finish.
After explicit acceptance, record it, set `COMPLETED / DONE / NONE`, increment the
state version, and validate.

## Remediator

Require exact Human-selected Finding IDs in `WORKFLOW.md`.

Fix only those IDs, append evidence to `40-execution.md`, update candidate HEAD,
validate, and return to a new Claude Review session.

## Human interaction

Never tell Human to edit Workflow Markdown or run the Validator.
When a Human decision is needed, present it clearly and stop.
