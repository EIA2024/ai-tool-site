# Quickstart

## 1. Start in Claude Code

```text
Start a new serial Workflow for this target:

<TARGET>

Follow CLAUDE.md and `.agent-workspace/protocol/`.

Act as Workflow Bootstrap, Project Context Scout, and Product Intent Facilitator:
- generate a unique Workflow ID;
- create the dedicated Workflow branch;
- create the six Workflow files from the templates;
- inspect the project sufficiently for this target;
- write `10-context.md`;
- discuss the intended behavior with me;
- identify unresolved product decisions;
- when the Intent is clear, present it for my confirmation;
- do not modify production code;
- do not hand off to Codex until I explicitly confirm the Intent.
```

When Claude presents:

```text
WAITING_FOR_HUMAN_INTENT_CONFIRMATION
```

reply naturally:

```text
确认 Intent
```

Claude writes and approves `20-intent.md`, validates the Workflow, and gives the
exact Codex Planning Prompt.

## 2. Plan in Codex

Paste Claude's Prompt into Codex.

Codex reads:

```text
WORKFLOW.md
10-context.md
20-intent.md
```

Codex writes `30-plan.md`, presents a Plan summary, and stops at:

```text
WAITING_FOR_HUMAN_PLAN_APPROVAL
```

Reply:

```text
批准计划
```

Codex records the approval, validates, and gives the exact Claude Executor Prompt.

## 3. Execute in Claude Code

Paste the Prompt into a fresh Claude session.

Claude executes only the approved Plan, runs tests, writes `40-execution.md`,
validates, and gives the exact Claude Review Prompt.

## 4. Review in a New Claude Session

Open a separate Claude session and paste the Review Prompt.

The Reviewer:

- reads Intent, Plan, Execution evidence, actual diff, commits, and tests;
- does not modify production code;
- writes `50-review.md`;
- returns `ACCEPT`, `REMEDIATE`, or `BLOCK`.

For remediation:

```text
修复 F-001 和 F-003
```

For acceptance:

```text
接受结果，结束 Workflow
```

The active Agent records every Human decision. Human does not edit files.
