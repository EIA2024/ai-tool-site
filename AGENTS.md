# AI Tool Site Agent Guide

## Purpose

AI Tool Site is a FastAPI + React plugin host for request-response and realtime
AI tools. Backend plugins define the contract; the frontend discovers and
renders them through the Host APIs.

## Run And Verify

- macOS local stack: `./start.sh`
- Windows local stack: `start.bat`
- Local mode uses SQLite and does not require PostgreSQL or Redis.
- Backend tests: `cd backend && .venv/bin/pytest`
- Backend lint: `cd backend && .venv/bin/ruff check .`
- Frontend checks: `cd frontend && npm test && npm run lint && npm run build`
- Compose validation: `docker compose config --quiet`

## Stack

- Backend: Python 3.11+, FastAPI, Pydantic, async SQLAlchemy, Alembic
- Frontend: React 19, TypeScript, Vite, Vitest
- Full stack: PostgreSQL 16, Redis 7, Docker Compose

## Structure And Conventions

- Backend plugins live in `backend/app/tool_plugins/<tool_id>/`.
- Custom frontend plugins live in `frontend/src/tool_plugins/<tool_id>/`.
- Plugins are auto-discovered; do not add central route or navigation entries.
- Operation handlers use the injected database session and never commit.
- The Host owns validation, transaction commit/rollback, errors, and auditing.
- Keep changes scoped and add regression tests for behavioral fixes.
- Never commit `.env`, credentials, local databases, caches, or build output.

## Current State

- The current architecture uses the unified Host/Plugin protocol for REST and
  WebSocket tools.
- Local startup scripts prepare dependencies, start both services, and clean up
  child processes on exit.
- Real model success paths require a valid provider API key; Docker, PostgreSQL,
  Redis, and provider integrations should be smoke-tested in their target
  environment before production deployment.
