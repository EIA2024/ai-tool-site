# Cross-Agent Takeover Protocol

## Principle

A takeover transfers externalized workflow state, not private conversation context.

## Normal takeover

Current agent:

1. Finish an atomic step.
2. Stop active commands and background processes, or document them.
3. Update State artifacts.
4. Write `checkpoint.json`.
5. Set `handoff_to` to the target agent or `any`.
6. Release `.workflow/runtime/agent-lock.json`.

New agent:

1. Start a fresh product session in the same Worktree.
2. Read the repository entry file.
3. Verify Branch–Run–State identity.
4. Read `state.json`, `checkpoint.json`, current State, and required artifacts.
5. Run `git status --short` and inspect the Diff.
6. Acquire the lock.
7. Continue from `next_action`.

## Recovery Mode

Use when the prior agent exited without a safe checkpoint.

The recovering agent must:

1. remain read-only initially;
2. inspect Branch, HEAD, status, Diff, and Run artifacts;
3. detect running processes when possible;
4. run the smallest non-destructive validation;
5. reconstruct a checkpoint;
6. record `recovered_by` and uncertainty;
7. request human input if ownership or intent remains ambiguous.

## Single-writer lock

File:

```text
.workflow/runtime/agent-lock.json
```

It is local and Git-ignored.

A second agent finding a lock may:

- operate read-only;
- ask the owner to release it;
- use explicit human-authorized forced takeover.

It may not write concurrently.

## Capability mismatch

Each State lists required capabilities.

If the new agent lacks one:

```text
state_status = blocked
reason = BLOCKED_BY_CAPABILITY
```

Do not skip the required action or claim equivalent evidence without justification.
