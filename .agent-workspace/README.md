# Agent Workspace

This directory contains the control plane for a serial Claude–Codex Workflow.

```text
Claude defines Intent
Codex creates the Plan
Claude executes
A fresh Claude session reviews independently
Markdown carries durable state
One read-only Validator checks mechanics
Human approves through Agent conversation
```

Product source code, tests, and normal documentation remain outside
`.agent-workspace/`.

Human never needs to edit Workflow Markdown or run routine validation commands.

This is organizational isolation, not an operating-system sandbox.
Do not store secrets, credentials, production data, or large source copies here.
