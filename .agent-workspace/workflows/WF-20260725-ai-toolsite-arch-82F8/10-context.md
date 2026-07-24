---
workflow_id: WF-20260725-ai-toolsite-arch-82F8
status: DRAFT
based_on_commit: a80e6f6
author_role: CLAUDE_CONTEXT_SCOUT
---

# Project Context

## Project Summary

- Purpose: Build an AI Tool Site — a web platform that integrates multiple AI-powered tools. The initial phase is to establish the full-stack architecture before any individual tool is implemented.
- Primary users: End-users who interact with various AI tools through the site.
- Main user flow: User provides input on the frontend → backend processes it (via server-side functions or AI API calls) → results are presented on the frontend. Some tools also require real-time bidirectional communication (e.g., chat interfaces via WebSocket).

## Relevant Structure

| Path or component | Responsibility | Relevance |
|---|---|---|
| `.agent-workspace/` | Workflow protocol, templates, validators, project context | Contains the development workflow harness |
| `CLAUDE.md` | Claude Code entry point with role definitions | Directs Claude behavior in this repo |
| `AGENTS.md` | Codex entry point | Directs Codex behavior for planning |
| `README.md` | Project overview | Currently a description of the workflow system, not the product |

## Current Relevant Behavior

- The repository is in its **initial state**: only workflow harness files and README exist.
- No product code, build configuration, or package manager files exist yet.
- No frontend or backend framework has been chosen.
- No database, API, or deployment configuration exists.

## Constraints to Preserve

- Execution and Review must use separate Claude sessions.
- Workflow files are managed by Agents, not by Human.
- Future tools are independent targets requiring new Workflow IDs.

## Project Vocabulary

| Term | Meaning |
|---|---|
| AI Tool | A discrete feature on the site that uses AI (API or local model) to process user input |
| Frontend | Browser-side UI for user interaction |
| Backend | Server-side logic for processing, AI API calls, WebSocket management |
| Real-time interaction | Bidirectional communication (WebSocket/SSE) between frontend and backend, e.g. chat streaming |

## Verified Facts

- Repository is a fresh git repo with master branch at commit a80e6f6.
- Working branch `agent/wf-20260725-ai-toolsite-arch-82f8` has been created.
- No package.json, requirements.txt, or any dependency file exists.
- No frontend or backend framework files exist.
- No CI/CD configuration exists.

## Uncertainties

- `UNVERIFIED` — User's preferred frontend framework (React, Vue, Svelte, etc.) is unknown.
- `UNVERIFIED` — User's preferred backend language/framework (Node.js, Python, Go, etc.) is unknown.
- `UNVERIFIED` — Whether the user wants SSR, SPA, or SSG for the frontend architecture.
- `UNVERIFIED` — Whether the user has preference for monorepo vs. separate frontend/backend repos.
- `UNVERIFIED` — Deployment target (self-hosted, Vercel, Railway, Docker, etc.).
- `UNVERIFIED` — Whether the user wants authentication, user management, API key management.
- `UNVERIFIED` — Database and storage requirements.
- `UNVERIFIED` — Whether real-time tools beyond chat are envisioned (e.g., streaming output, live collaboration).

## Raw Target

Build an AI Tool Site with full-stack architecture supporting:
1. Request-response flow: frontend input → backend processing (functions / AI APIs) → frontend display
2. Real-time bidirectional flow: WebSocket-like persistent connection (e.g., chat, streaming)

The architecture should be extensible so that new tools can be added incrementally.

## Coverage and Safety

- Areas inspected: repository root, all existing files.
- Areas not inspected: no external dependencies or environments have been set up.
- Sensitive information intentionally omitted: N/A.

## Handoff

<USE .agent-workspace/protocol/HANDOFF_TEMPLATE.md>
