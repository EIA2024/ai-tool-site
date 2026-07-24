# Claude Code Entry

This repository uses the final Claude–Codex Prompt-native Workflow.

Always read:

1. `.agent-workspace/protocol/WORKFLOW_PROTOCOL.md`
2. `.agent-workspace/protocol/HANDOFF_TEMPLATE.md`
3. `.agent-workspace/protocol/CLAUDE_RULES.md`
4. the exact `.agent-workspace/workflows/<WORKFLOW_ID>/WORKFLOW.md`

Claude roles:

- Workflow Bootstrap;
- Project Context Scout;
- Product Intent Facilitator;
- Executor;
- Independent Reviewer;
- Remediator.

Execution and Review must use separate Claude sessions.
A Reviewer must not modify production code.

Require the full Workflow ID after bootstrap.
Never infer a Workflow from target similarity.
Never read sibling Workflow artifacts unless the current Workflow explicitly
authorizes one exact immutable dependency.
