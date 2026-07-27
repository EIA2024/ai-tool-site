# Run Protocol

## Run identity

Format:

```text
WF-YYYYMMDD-NNN-short-slug
```

The ID is permanent and never reused.

A Run is bound to:

```text
branch: workflow/<run-id>
worktree: dedicated path
artifacts: .workflow/runs/<run-id>/
```

## Run statuses

```text
registered
active
blocked
awaiting_approval
candidate_frozen
merge_queued
returned_for_changes
integrating
merged
cancelled
terminal_failed
retro_complete
archived
```

## Nine-State lifecycle

```text
S1_GOAL
S2_RESEARCH
S3_SPECIFICATION
S4_PLANNING
S5_IMPLEMENTATION
S6_VALIDATION
S7_REVIEW
S8_CANDIDATE
[Master Integration]
S9_RETRO
```

S9 runs only after `merged`, `cancelled`, or `terminal_failed`.

## Forward transitions

- S1 → S2: Goal version approved.
- S2 → S3: blocking unknowns resolved; evidence recorded.
- S3 → S4: acceptance criteria are testable.
- S4 → S5: exact Plan version approved.
- S5 → S6: approved implementation scope complete.
- S6 → S7: required validation passed.
- S7 → S8: no Blocker and accepted risks recorded.
- S8 → merge queue: exact candidate SHA frozen and approved.
- terminal outcome → S9: merge/cancellation/failure outcome recorded.

## Backward routing

- implementation defect → S5;
- validation design defect → S6;
- plan invalidated → S4 and old Plan approval invalid;
- specification ambiguity → S3;
- goal conflict/change → S1;
- integration regression → returned to S5/S6/S7 based on cause.

## Candidate freeze

S8 must create a clean Commit and record:

```text
candidate_sha
source_branch
validation_for_sha
review_for_sha
impact_for_sha
```

After freeze:

- child branch is read-only;
- any new Commit invalidates candidate approval, S6 evidence, and S7 review;
- Master integrates only the recorded SHA;
- changes require `returned_for_changes`.

## Run artifact isolation

A child Run may read:

- its own Run directory;
- stable project files;
- explicitly declared completed dependencies.

It may not consume another Run's intermediate artifacts by default.
