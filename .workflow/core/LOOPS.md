# Loop and Failure Control

## Default budget

```text
same_error_retries: 2
implementation_iterations: 4
validation_fix_cycles: 3
review_fix_cycles: 2
replans: 2
integration_attempts: 2
```

## Plateau indicators

- same or equivalent error appears twice;
- two iterations do not reduce failures;
- the same Diff is repeatedly added and reverted;
- the same command is repeated without a changed hypothesis;
- progress requires violating approved Goal/Spec/Plan;
- explanation repeats without new evidence.

## Required response to plateau

Choose one:

- change strategy;
- gather missing evidence;
- route to an earlier State;
- request human decision;
- mark terminal failure.

Never continue the unchanged strategy beyond the budget.

## Failure ownership

- environment transient → bounded retry;
- local code defect → S5;
- validation design issue → S6;
- plan invalid → S4;
- specification ambiguity → S3;
- goal conflict → S1;
- capability mismatch → blocked;
- security/irreversible action → human escalation;
- integration-only regression → Master classifies and returns Run(s).
