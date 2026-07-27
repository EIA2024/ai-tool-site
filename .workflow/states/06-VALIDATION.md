# S6 — Validation

Purpose: prove correctness against the current Spec.

Use applicable external sensors:

- build;
- typecheck;
- lint;
- unit/integration/acceptance tests;
- reproducible runtime behavior;
- security/performance checks where required.

Every acceptance criterion is:

```text
PASS / FAIL / NOT RUN / NOT APPLICABLE
```

Record exact commands and results.

Implementation defect → S5.
Plan defect → S4.
Spec ambiguity → S3.
