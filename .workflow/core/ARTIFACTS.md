# Artifact Contracts

Every Run artifact contains the Run ID and is scoped to one Workflow.

## Machine artifacts

### `state.json`

Authoritative workflow state:

- Run identity and Git binding;
- lifecycle status and State;
- versions and approvals;
- Loop budget/use;
- candidate SHA and freeze status;
- last/current agent metadata;
- required artifacts;
- next action.

### `checkpoint.json`

Portable takeover state:

- current State and step;
- HEAD and dirty status;
- completed and pending work;
- changed files;
- validation evidence;
- failed attempts;
- active processes;
- risks;
- exact next action;
- creator and intended recipient.

### `impact.json`

Both planned and actual impact:

- files and modules;
- interfaces;
- behavior;
- data models;
- configuration;
- dependencies;
- migrations;
- project-level proposals.

## Human-readable artifacts

- `goal.md`
- `research.md`
- `spec.md`
- `plan.md`
- `progress.md`
- `validation.md`
- `review.md`
- `candidate.md`
- `retro.md`
- `decisions.md`
- `transitions.md`

## Version invalidation

- Goal version changes invalidate downstream Spec/Plan approval as applicable.
- Spec version changes invalidate Plan approval and dependent implementation assumptions.
- Plan version changes invalidate old Plan approval.
- Candidate SHA changes invalidate candidate approval, validation, and review.
- Integration SHA changes invalidate integration approval.
