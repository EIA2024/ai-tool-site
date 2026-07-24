# Workflow Instances

Each target creates:

```text
.agent-workspace/workflows/<WORKFLOW_ID>/
```

The first local Agent scans this directory, creates a unique immutable ID, and
copies the six templates.

There is no global `ACTIVE.md`.

This final harness runs Workflows serially.
