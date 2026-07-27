# Local Experiment Checklist

## A. Framework initialization

- [ ] Package copied to repository root.
- [ ] Project context files completed.
- [ ] Framework committed to `main`.
- [ ] `workflow.ps1 doctor` passes.
- [ ] Git supports Worktrees.
- [ ] Claude Code Desktop and Codex can both open a chosen local Worktree.

## B. Single-agent baseline

- [ ] Create one Run.
- [ ] Complete S1–S4 with one agent.
- [ ] Approvals bind to Run ID and versions.
- [ ] Continue S5–S7 with the same agent.
- [ ] Freeze a clean candidate SHA.

## C. Cross-agent takeover

- [ ] Agent A acquires lock.
- [ ] Agent A completes one atomic step.
- [ ] Agent A writes checkpoint.
- [ ] Agent A releases lock.
- [ ] Agent B opens a fresh session in the same Worktree.
- [ ] Agent B verifies Branch, Run, HEAD, status, and checkpoint.
- [ ] Agent B acquires lock and continues without restarting.
- [ ] No unrecorded decision is required.

## D. Parallel Runs

- [ ] Create two Runs and two Worktrees.
- [ ] Each Worktree has a distinct branch and Run directory.
- [ ] Agents cannot modify another Run's artifacts.
- [ ] Runtime locks are independent.
- [ ] Project control files are not edited by child agents.

## E. Integration

- [ ] Both candidates have immutable SHAs.
- [ ] Candidate approval matches SHA.
- [ ] Master uses a dedicated integration Worktree.
- [ ] Text and semantic overlaps are reviewed.
- [ ] Combined validation runs.
- [ ] Integration approval matches integration SHA.
- [ ] S9 runs only after terminal outcome.

## F. Adversarial cases

- [ ] Agent exits without checkpoint; Recovery Mode succeeds.
- [ ] Second agent encounters existing lock and remains read-only.
- [ ] Candidate is changed; old approval and evidence are rejected.
- [ ] A Plan version changes; old approval is rejected.
- [ ] Git auto-merges but integration test catches semantic conflict.
- [ ] Capability mismatch blocks rather than silently skipping work.
