# S4 — Planning

Purpose: select the smallest sufficient solution and create an executable Plan.

Required:

- alternatives where meaningful;
- decision and trade-offs;
- exact file/module scope;
- ordered atomic steps;
- validation per step;
- risks, dependencies, rollback;
- planned `impact.json`;
- Plan version.

Forbidden:

- business-code changes;
- scope expansion;
- self-approval.

Exit:

```text
APPROVE PLAN <run-id> vN
```
