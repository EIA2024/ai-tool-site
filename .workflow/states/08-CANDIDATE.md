# S8 — Candidate Freeze

Purpose: produce an immutable, reviewed merge candidate.

Requirements:

- working tree clean;
- implementation committed;
- candidate SHA recorded;
- validation and review explicitly bound to the same SHA;
- actual impact complete;
- dependencies and risks declared;
- candidate summary written.

After freeze the child branch is read-only.

Human token:

```text
APPROVE CANDIDATE <run-id> <candidate-sha>
```

Only the Master may enqueue and integrate the candidate.
