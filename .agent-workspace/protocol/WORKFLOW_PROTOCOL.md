# Claude–Codex Prompt-Native Workflow Protocol

## 1. Workflow identity

Each independent target gets one immutable ID:

```text
WF-YYYYMMDD-<slug>-<4 uppercase hex>
```

The first Claude session scans `.agent-workspace/workflows/` before creating it.

Every cross-Agent Prompt includes:

```text
WORKFLOW_ID
EXPECTED_STATE_VERSION
ROLE
WORKFLOW_PATH
```

Never infer or auto-discover a Workflow from target similarity.

## 2. Serial execution

This harness is intentionally serial.

- Human runs only one active code-changing Workflow at a time.
- Historical and future Workflow directories may coexist.
- The harness does not provide parallel locks or cross-worktree coordination.

## 3. Six Workflow files

```text
WORKFLOW.md
10-context.md
20-intent.md
30-plan.md
40-execution.md
50-review.md
```

All files carry the same `workflow_id`.

## 4. Stages

```text
SCOUTING
HUMAN_INTENT_REVIEW
CODEX_PLANNING
HUMAN_PLAN_REVIEW
CLAUDE_EXECUTION
CLAUDE_REVIEW
REMEDIATION
DONE
BLOCKED
```

`state_version` increments at every formal Agent handoff or Human decision.

## 5. Dedicated branch

A new Workflow normally uses:

```text
agent/<workflow-id-lowercase>
```

Claude Bootstrap creates or switches to this branch before writing Workflow files.

## 6. Role authority

### Claude Bootstrap + Context Scout + Intent Facilitator

Owns:

- Workflow creation;
- `WORKFLOW.md`;
- `10-context.md`;
- `20-intent.md`.

Claude reads the project, discusses the target with Human, separates product intent
from implementation choices, and persists the confirmed Intent.

Claude must not modify production code during this phase.

### Codex Planner

Owns `30-plan.md`.

Codex translates confirmed Intent into an implementation Plan.
It must not redefine product intent, modify production code, or perform final Review.

### Claude Executor

Owns approved code/test changes and `40-execution.md`.

It cannot rewrite confirmed Intent or approved Plan.

### Claude Independent Reviewer

Owns `50-review.md`.

Review must run in a separate Claude session from Execution.

The Reviewer:

- independently reads Intent, Plan, Execution evidence, actual diff, commits, and tests;
- evaluates correctness, scope, regressions, security, and acceptance criteria;
- writes stable Finding IDs;
- returns `ACCEPT`, `REMEDIATE`, or `BLOCK`;
- must not modify production code.

### Claude Remediator

May fix only the exact Finding IDs selected by Human.

### Human

Approves only through normal Agent conversation.
Human never edits Workflow files or runs routine validators.

## 7. Conversational Intent confirmation

Claude presents:

```text
WAITING_FOR_HUMAN_INTENT_CONFIRMATION
```

Only an unambiguous Human response counts.

Claude then approves `20-intent.md`, records the decision, increments
`state_version`, moves to `CODEX_PLANNING`, validates, and generates the Codex Prompt.

## 8. Conversational Plan approval

Codex presents:

```text
WAITING_FOR_HUMAN_PLAN_APPROVAL
```

After explicit Human approval, Codex records approval metadata, updates
`WORKFLOW.md`, moves to `CLAUDE_EXECUTION`, validates, and generates the Claude
Executor Prompt.

## 9. Independent Claude Review

After Execution, Claude Executor:

1. writes `40-execution.md`;
2. sets stage and owner to `CLAUDE_REVIEW`;
3. runs the Validator;
4. generates a Review Prompt for a new Claude session.

The Reviewer must not rely on the Executor's chat memory.
It must read the durable Workflow files and repository evidence directly.

## 10. Remediation selection

The Claude Reviewer uses stable Finding IDs such as `F-001`.

Human selects exact IDs in conversation.
The current Claude Reviewer records them under:

```text
WORKFLOW.md → approved_remediation_findings
```

Then it sets stage to `REMEDIATION`, validates, and generates a Claude Remediation
Prompt.

## 11. Completion

For `ACCEPT`, the Claude Reviewer asks Human whether to finish.

After explicit acceptance, it records the decision, sets Workflow status
`COMPLETED`, stage `DONE`, owner `NONE`, increments `state_version`, and validates.

## 12. Handoff rule

Every completed stage must:

1. update its owned file;
2. update `WORKFLOW.md`;
3. run the Validator itself;
4. write a complete `## Handoff`;
5. show the same Handoff in chat.

Human must not be asked to compose the next Prompt or run routine validation.

## 13. Validator

Agents run:

```text
python .agent-workspace/validators/validate_workflow.py \
  --workflow <WORKFLOW_ID>
```

It is read-only and does not:

- create Workflows;
- update stages;
- approve artifacts;
- generate Prompts;
- decide product meaning.

## 14. Context freshness

Before Codex planning and Plan approval, Codex checks whether product files changed
after `10-context.md`'s `based_on_commit`.

Changes under `.agent-workspace/` alone do not stale Context.

## 15. Isolation

Agents may read:

- root Agent entry files;
- `.agent-workspace/protocol/`;
- `.agent-workspace/project/`;
- the exact current Workflow;
- repository files needed by the role.

Sibling Workflow artifacts are denied by default.

## 16. Stop conditions

Stop with `BLOCKED` when:

- Workflow ID is missing or inconsistent;
- current branch is wrong;
- Stage and Owner disagree;
- Context is stale before Plan approval;
- Intent is not Human-confirmed;
- Plan is not Human-approved;
- repository reality invalidates the approved Plan;
- Review is attempted in the Executor's existing session;
- Reviewer modifies production code;
- Handoff is incomplete;
- template placeholders remain;
- scope expands beyond the approved target;
- remediation IDs were not explicitly selected by Human.
