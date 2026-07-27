# Cross-Agent Workflow Bootstrap

This repository uses an agent-independent workflow. Claude Code and Codex may both execute any legal workflow State and may take over from one another only at a recorded safe checkpoint.

Before any action:

1. Read `.workflow/core/PROTOCOL.md`.
2. Determine the current Git branch and repository root.
3. Derive the Run ID from a branch named `workflow/<run-id>`.
4. Read `.workflow/runs/<run-id>/state.json`.
5. Read `.workflow/runs/<run-id>/checkpoint.json`.
6. Read the current State file under `.workflow/states/`.
7. Verify the Branch–Run–State ownership invariants.
8. Acquire the local agent lock before writing.
9. Continue from `next_action`; do not restart the workflow by default.

When operating on `main` or an `integration/*` branch, read `.workflow/roles/MASTER-INTEGRATOR.md` and `.workflow/core/INTEGRATION-PROTOCOL.md`.

Authoritative state is stored in Git and `.workflow/`. Chat history, private reasoning, product-specific memory, UI task lists, and unrecorded decisions are never authoritative.

Do not commit, push, merge, deploy, migrate, delete data, or perform irreversible actions unless the applicable workflow Gate and explicit human authorization have been recorded.
