# Human Approval Protocol

Exact tokens:

```text
APPROVE GOAL <run-id> vN
APPROVE PLAN <run-id> vN
APPROVE CANDIDATE <run-id> <candidate-sha>
APPROVE INTEGRATION <integration-id> <integration-sha>
ACCEPT RISK <run-id> <risk-id>
AUTHORIZE ACTION <run-id> <action-id>
FORCE TAKEOVER <run-id> BY <agent>
```

Rules:

1. Agents may not infer approval from casual language.
2. Agents may not create approval tokens on behalf of the user.
3. Approval must be written into `decisions.md` and `state.json`.
4. Version or SHA changes invalidate the previous approval.
5. Candidate approval does not authorize merge, push, deploy, or migration.
6. Integration approval authorizes only the reviewed integration SHA and the explicitly described merge action.
