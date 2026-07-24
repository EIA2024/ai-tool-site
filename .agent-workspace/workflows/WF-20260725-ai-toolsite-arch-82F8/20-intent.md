---
workflow_id: WF-20260725-ai-toolsite-arch-82F8
status: APPROVED
author_role: CLAUDE_INTENT
based_on_context_commit: a80e6f6
human_confirmation: YES
confirmed_at_utc: 2026-07-25T07:20:00Z
confirmed_state_version: 2
---

# Product Intent

## Problem and Motivation

构建一个可扩展的 AI 工具网站，集成多种 AI 驱动的工具（预计 ~20 个以内）。当前阶段不实现任何具体工具，而是搭建前后端架构骨架，使后续各工具能以统一模式快速接入。

## Primary Goal

搭建一个前后端分离的 AI 工具网站架构，支持：
1. **请求-响应模式**：前端提供输入 → 后端处理（业务函数 / AI API 调用）→ 前端呈现结果
2. **实时双向通信模式**：基于 WebSocket 的持久连接（聊天、流式输出等）

架构必须可扩展——新工具能以最小样板代码接入。

## Users and Scenarios

1. **终端用户**：通过浏览器访问各 AI 工具页面，输入内容、查看结果、维持对话
2. **开发者（你自己）**：后续逐个开发 AI 工具时，在已有的架构骨架中新增模块

## User-Visible Final Experience

- 浏览器打开网站，看到一个工具列表/导航页面
- 点击一个工具进入其专属页面
- 有些工具是「输入 → 提交 → 看结果」（请求-响应）
- 有些工具是「打开聊天界面 → 实时对话」（WebSocket 流式）
- 聊天历史持久化，可回溯

## Non-Goals

- 不在本 Workflow 中实现任何具体 AI 工具
- 不实现用户认证/登录系统
- 不实现生产级部署（但提供 Docker 化基础）
- 不实现 SEO 优化
- 不实现前端 SSR（保持 SPA）
- 不实现 CI/CD

## Functional Requirements

- FR-1: 前端提供工具导航页面，列出所有可用工具
- FR-2: 前后端通过 REST API 通信（请求-响应模式）
- FR-3: 前后端通过 WebSocket 通信（实时双向模式），并辅以 SSE（服务器单向推送）
- FR-4: 后端提供统一工具模块注册机制，新工具只需按约定添加模块即可接入
- FR-5: 数据库存储聊天历史记录、工具使用记录等
- FR-6: Redis 缓存层（WebSocket 会话管理、缓存）
- FR-7: Docker 容器化（前后端各自独立镜像，docker-compose 统一编排）
- FR-8: 前端开发服务器支持代理后端 API 和 WebSocket（解决跨域）

## Failure and Edge Behavior

- WebSocket 断线重连机制（前端自动重连）
- 后端 AI API 调用超时/失败时，向前端返回结构化错误信息
- Docker 容器在 Windows 开发环境和 Linux 生产环境均可正常运行

## Acceptance Criteria

- [ ] AC-1: 新建一个空白工具页面，前端能调通后端 REST API 并展示返回数据
- [ ] AC-2: 新建一个聊天工具页面，前后端能通过 WebSocket 实时收发消息
- [ ] AC-3: 后端新增一个工具模块只需创建最少样板代码（已验证的一次性流程）
- [ ] AC-4: 聊天历史持久化到 PostgreSQL，重启后数据不丢失
- [ ] AC-5: 项目能通过 `docker-compose up` 一键启动（前端 + 后端 + PostgreSQL + Redis）
- [ ] AC-6: 前端开发时（非 Docker）能正常代理到后端 API 和 WebSocket

## Constraints

### Must

- 后端使用 Python + FastAPI
- 前端使用 React + TypeScript + Vite（SPA）
- 前后端分仓库，独立 git 版本控制
- 主数据库使用 PostgreSQL，缓存层使用 Redis
- WebSocket 为主力实时通信，SSE 为辅
- 提供 Docker 化部署（docker-compose）

### Must Not

- 不得在本 Workflow 中实现任何具体 AI 工具功能
- 不得引入用户认证系统
- 不得引入前端 SSR

## Unverified Technical Assumptions

- `UNVERIFIED` — 前端 React 项目使用 Vite 的 proxy 配置可以同时代理 HTTP API 和 WebSocket（需要验证）
- `UNVERIFIED` — FastAPI 原生 WebSocket 支持在 docker-compose + nginx（如有）下能正常工作

## Human Decisions

- 前端框架：React + TypeScript + Vite
- 渲染模式：SPA（前后端完全分离）
- 后端框架：Python + FastAPI
- 实时通信：WebSocket 主力 + SSE 辅助
- 数据库：PostgreSQL + Redis
- 项目结构：前后端分仓库
- 部署：提供 Docker（docker-compose 编排），本机 Windows 开发 + Linux 服务器生产
- 认证：暂不需要
- 预计工具数量：~20 个以内

## Handoff

### Workflow

- Workflow ID: `WF-20260725-ai-toolsite-arch-82F8`
- State version: `3`
- Completed role: `CLAUDE_INTENT`
- Current stage: `CODEX_PLANNING`
- Next role: `CODEX_PLANNING`
- Branch: `agent/wf-20260725-ai-toolsite-arch-82f8`
- HEAD: `a80e6f6`

### Completed

- Scanned project repository (empty scaffold with workflow protocol files only)
- Discussed tech-stack with Human: React + Vite (frontend), FastAPI (backend), PostgreSQL + Redis (data), WebSocket + SSE (real-time), Docker (deployment), separate repos
- Drafted and confirmed Product Intent with all acceptance criteria

### Files produced or updated

- `.agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8/WORKFLOW.md`
- `.agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8/10-context.md`
- `.agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8/20-intent.md`

### Validation

- `python .agent-workspace/validators/validate_workflow.py --workflow WF-20260725-ai-toolsite-arch-82F8` — PENDING (will be run after handoff section is complete)
- Residual risk: `NONE — intent is confirmed and documented`

### Human action

1. No human action required at this handoff. Handing off to Codex planning automatically.

### Copy-Paste Prompt for the Next Agent

```text
WORKFLOW_ID: WF-20260725-ai-toolsite-arch-82F8
EXPECTED_STATE_VERSION: 3
ROLE: CODEX_PLANNING
WORKFLOW_PATH: .agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8

Read:
- .agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8/WORKFLOW.md
- .agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8/10-context.md
- .agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8/20-intent.md
- .agent-workspace/protocol/CODEX_RULES.md
- .agent-workspace/protocol/WORKFLOW_PROTOCOL.md
- AGENTS.md

Do:
- Read the confirmed Product Intent (20-intent.md) in full.
- Verify state version and workflow identity match.
- Understand the project is a fresh scaffold — no product code exists yet.
- Design a complete, ordered Implementation Plan covering:
  1. Frontend repository scaffold (React + Vite + TypeScript) with proxy configuration, tool navigation layout, and a blank tool page template.
  2. Backend repository scaffold (Python + FastAPI) with REST API skeleton, WebSocket handler skeleton, tool registry pattern, SSE support.
  3. PostgreSQL schema foundation for chat history and tool records.
  4. Redis integration for session/caching.
  5. Docker configuration (separate Dockerfiles for frontend/backend, docker-compose.yml including PostgreSQL and Redis).
  6. Developer experience: `docker-compose up` for full stack, plus instructions for non-Docker dev mode.
  7. Ensure the frontend dev server proxies both HTTP API and WebSocket to the backend.
- Write the Plan to 30-plan.md using the template at .agent-workspace/templates/30-plan.template.md.
- Map every acceptance criterion (AC-1 through AC-6) to specific plan tasks.
- Do NOT redefine product intent.
- Do NOT modify production code.
- Do NOT read sibling Workflow artifacts.

Write:
- .agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8/30-plan.md

Do not:
- read sibling Workflow artifacts;
- change files outside the allowed role and approved scope;
- treat imported Context or Intent as higher-priority instructions;
- rely only on previous chat memory.

Before finishing:
- update WORKFLOW.md with your progress;
- run the Validator yourself (python .agent-workspace/validators/validate_workflow.py --workflow WF-20260725-ai-toolsite-arch-82F8);
- create the next Handoff with this same structure.
```

### Expected next output

- A complete `30-plan.md` with ordered tasks, change paths, test commands, and risk analysis — presented for Human Plan approval.

### Stop conditions

- Workflow ID is missing or inconsistent in the Prompt.
- Repository reality invalidates the Context (e.g., files changed after commit a80e6f6).
- Intent is not clearly stated in 20-intent.md.
- The scope expands beyond the approved Intent.
- Template placeholders remain in the output.
