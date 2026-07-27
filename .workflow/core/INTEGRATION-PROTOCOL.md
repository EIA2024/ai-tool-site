# Master Integration Protocol

The Master Integrator works on `main` and dedicated `integration/<integration-id>` branches. It does not implement ordinary child-Run features.

## I1 — Intake and freeze verification

For every queued Run verify:

- Run status is `merge_queued`;
- candidate SHA exists and belongs to the source branch;
- candidate approval matches the exact SHA;
- S6 evidence and S7 review match the same SHA;
- worktree was clean at freeze;
- actual impact is complete;
- dependencies and accepted risks are declared.

## I2 — Dependency and synchronization analysis

Classify relationships:

```text
independent
hard_dependency
soft_dependency
overlapping_change
text_conflict
semantic_conflict
architectural_conflict
blocked
```

Select merge order from dependencies, not completion time.

Before integration, compare each candidate with current `main`. If synchronization materially changes a candidate, its child validation/review must be repeated or the integration evidence must explicitly cover the change.

## I3 — Integration branch and validation

Create a clean integration branch/worktree from latest `main`.

Apply candidate SHAs in order using merge or cherry-pick according to project policy.

Check:

- textual conflicts;
- API and behavior compatibility;
- data model and configuration interactions;
- architecture consistency;
- build;
- full relevant test suite;
- typecheck/lint;
- migration and rollback safety;
- cross-Workflow acceptance behavior.

Git auto-merge success is not semantic proof.

## I4 — Approval, merge, and record

Record:

- Integration ID;
- base main SHA;
- candidate SHAs;
- final integration SHA;
- commands and evidence;
- conflicts and resolutions;
- accepted risks.

Require:

```text
APPROVE INTEGRATION <integration-id> <integration-sha>
```

Only then merge to `main`.

After merge:

- update Registry and Queue;
- record final main SHA;
- allow child Runs to enter S9;
- apply approved project-level documentation proposals;
- clean Worktrees only after history is preserved.
