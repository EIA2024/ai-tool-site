# Security Audit Remediation Task

**Status:** PENDING
**Created:** 2026-07-25
**Source:** Adversarial security review (37 findings)
**Plan file:** `.claude/plans/bug-cosmic-dragonfly.md`

## Execution Workflow

Run phases in order. Each phase depends on the previous completing without regressions.

### Phase 1 — Critical (do first)
- [ ] P1-C1: Add API authentication (JWT/API-key)
- [ ] P1-C2: Stop accepting user-supplied session_api_key when server key exists
- [ ] P1-C3: Tighten CORS config (no wildcards)
- [ ] P1-C4: Remove hardcoded postgres:postgres from all config files
- [ ] P1-C5: Replace root .gitignore

### Phase 2 — High
- [ ] P2-H1: Stop leaking exception messages to clients
- [ ] P2-H2: Add Pydantic input validation at route level
- [ ] P2-H3: Add rate limiting (slowapi)
- [ ] P2-H4: Prompt injection defense
- [ ] P2-H5: WebSocket Origin validation + auth
- [ ] P2-H6: Frontend API key transport security
- [ ] P2-H7: Enable TypeScript strict mode
- [ ] P2-H8: fetch HTTP status checking
- [ ] P2-H9: Docker containers run as non-root
- [ ] P2-H10: Pin dependencies / generate lock file
- [ ] P2-H11: Remove datastore port exposure
- [ ] P2-H12: Fix misleading INTERNAL_ERROR test

### Phase 3 — Medium
- [ ] P3-M1: Wire get_db() dependency
- [ ] P3-M2: Fix non-atomic duplicate check (race condition)
- [ ] P3-M3: Add pagination to list_records
- [ ] P3-M4: Redis health check + auto reconnect
- [ ] P3-M5: Fix frontend env var naming + production 404
- [ ] P3-M6: History error displayed in UI
- [ ] P3-M7: WebSocket security (no plaintext payloads, URL resolution)
- [ ] P3-M8: Frontend null guards + CSP headers
- [ ] P3-M9: Backend volume mount scoping
- [ ] P3-M10: Remove unused psycopg2-binary

### Phase 4 — Low
- [ ] P4-L1: Remove version from /api/health
- [ ] P4-L2: Second-stage prompt injection cleanup
- [ ] P4-L3: Clear API key from React state after submit
- [ ] P4-L4: WebSocket message stable keys
- [ ] P4-L5: AbortController for analyzeTask
- [ ] P4-L6: Constrain role column to enum
- [ ] P4-L7: Remove dead ToolCallRecord table
- [ ] P4-L8: Docker entrypoint script (SIGTERM handling)
- [ ] P4-L9: Update workflow repository_head
