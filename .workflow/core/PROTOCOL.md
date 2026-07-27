# Core Protocol

## 1. First principles

The workflow exists to preserve four kinds of truth:

1. **Project truth** — the current `main` branch.
2. **Run truth** — the current `workflow/<run-id>` branch and Run artifacts.
3. **Candidate truth** — an immutable reviewed candidate Commit SHA.
4. **Integration truth** — an integration Commit validated against current `main`.

Every fact has one authoritative location. Duplicate indexes are advisory only.

## 2. Authority order

1. Explicit current human decision recorded in Run artifacts.
2. Current Git branch, Commit, working tree, and actual command output.
3. Current Run `state.json`.
4. Current Run `checkpoint.json`.
5. Current approved Goal, Spec, and Plan.
6. Stable files under `.workflow/project/`.
7. Shared workflow protocol.
8. Conversation history and model inference.

## 3. Branch ownership

A child agent may write only when all are true:

```text
branch = workflow/<run-id>
state.run_id = <run-id>
state.branch = current branch
current repository root = registered worktree
local lock is free or owned by this agent
candidate status is not frozen
```

Any mismatch requires immediate stop.

## 4. State execution

Before a State:

- read the State file;
- verify required inputs and versions;
- verify approval requirements;
- verify capability requirements;
- verify Loop budget;
- inspect actual Git status;
- acquire the local lock before writing.

After meaningful work:

- update the relevant artifacts;
- update `state.json`;
- write a safe checkpoint;
- append `transitions.md` when State changes;
- report evidence and open risks.

## 5. External evidence

The following outrank model self-assessment:

- Git status, Diff, Commit SHA;
- compiler/build output;
- tests;
- type checking and linting;
- reproducible runtime behavior;
- user approval;
- independent review findings.

Never claim a command ran unless it actually ran.

## 6. Safe checkpoints

A checkpoint is safe only when:

- no command or migration is still running;
- files are syntactically coherent;
- partial experiments are identified;
- changed files are listed;
- validation evidence is recorded;
- failed attempts are recorded;
- next action is explicit;
- lock can be released.

Agent switching outside a safe checkpoint is Recovery Mode.

## 7. Product independence

Claude Code and Codex may execute any State. The protocol never assigns a State permanently to a product.

Product-specific memory, hidden plans, UI todos, and conversation context are non-portable and non-authoritative.

## 8. Protected actions

Child agents may not:

- edit another Run directory;
- edit `.workflow/control/`;
- edit stable `.workflow/project/` files directly;
- merge into `main`;
- push, deploy, migrate, or delete data without explicit authorization;
- modify a frozen candidate;
- silently expand Goal, Spec, or Plan.

Project-level updates are proposed in the Run and applied by the Master after approval.
