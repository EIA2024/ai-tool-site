---
workflow_id: WF-20260725-ai-toolsite-arch-82F8
status: APPROVED
author_role: CODEX_PLANNING
based_on_commit: 33bf622
human_approval: YES
approved_at_utc: 2026-07-24T20:44:46Z
approved_state_version: 4
approved_head_commit: 33bf622
---

# Implementation Plan

## Goal and Acceptance Mapping

| Acceptance criterion | Plan task |
|---|---|
| AC-1: 新建一个空白工具页面，前端能调通后端 REST API 并展示返回数据 | T-2 前端 SPA 骨架与空白工具页模板；T-4 FastAPI REST 骨架与空白工具接口；T-8 联调与 smoke 验证 |
| AC-2: 新建一个聊天工具页面，前后端能通过 WebSocket 实时收发消息 | T-3 前端聊天页模板与 WebSocket 客户端；T-4 WebSocket/SSE 服务端骨架；T-8 实时通信验证 |
| AC-3: 后端新增一个工具模块只需创建最少样板代码 | T-5 工具注册表与模块约定；T-8 新增示例工具接入流程验证 |
| AC-4: 聊天历史持久化到 PostgreSQL，重启后数据不丢失 | T-6 PostgreSQL schema、ORM/migration 骨架与历史读写路径；T-8 重启后持久化验证 |
| AC-5: 项目能通过 `docker-compose up` 一键启动 | T-1 仓库/目录基线；T-7 Dockerfiles、compose、环境变量与启动脚本；T-8 全栈容器启动验证 |
| AC-6: 前端开发时（非 Docker）能正常代理到后端 API 和 WebSocket | T-2 Vite dev proxy；T-8 非 Docker 开发链路验证 |

## Verified Repository Findings

- 当前 Workflow ID、路径与用户指令一致：`WF-20260725-ai-toolsite-arch-82F8`。
- `WORKFLOW.md` 当前处于 `CODEX_PLANNING`，`state_version: 3`，与进入本阶段的输入一致。
- 当前分支为 `agent/wf-20260725-ai-toolsite-arch-82f8`，符合协议要求。
- 当前 `HEAD` 为 `33bf622`。
- `20-intent.md` 已是 `APPROVED`，且 `human_confirmation: YES`。
- 自 `10-context.md` 的 `based_on_commit: a80e6f6` 以来，仅 `.agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8/` 内文件发生变化，没有产品代码变化，因此 Context 未失效。
- 仓库仍是 fresh scaffold：根目录只有 workflow harness 文件、`README.md`、`AGENTS.md`、`CLAUDE.md`，尚无前端、后端、数据库、Docker 或依赖管理文件。

## Approach

- 以最小可运行骨架为目标，先打通“目录结构 + 开发链路 + 容器链路 + 数据基础设施”，不实现任何具体 AI 工具业务。
- 前端使用 `React + Vite + TypeScript` 的 SPA，内置工具导航、空白工具页模板、聊天页模板，以及统一的 REST / WebSocket 客户端层。
- 后端使用 `FastAPI` 提供 REST、WebSocket、SSE 三类入口，并通过工具注册表模式承载后续工具扩展。
- 数据层只建设基础表与迁移链路，覆盖聊天会话、聊天消息、工具调用记录三类核心对象。
- Redis 只承担当前阶段已确认的职责：会话/连接元数据与缓存；不提前引入未被需求要求的复杂消息总线。
- Docker 以本地开发优先：前端、后端各自独立 Dockerfile，根目录 `docker-compose.yml` 编排 PostgreSQL、Redis、前后端四个服务。
- 由于 Intent 要求“前后端分仓库、独立 git 版本控制”，执行时需要把 `frontend/` 与 `backend/` 组织为可独立演进的边界；若必须立即创建两个真正独立的远端仓库或嵌套 `.git`，执行阶段在落地前需先确认目标托管位置。

## Ordered Tasks

### T-1 — Workspace Baseline And Repo Boundaries

- Purpose: 建立前后端分离的目录基线、统一端口与环境变量约定，为后续 scaffold 和 Docker 编排提供稳定结构。
- Files or symbols:
  - `frontend/`
  - `backend/`
  - `docker-compose.yml`
  - `.env.example`
  - `docs/development.md`
- Required change:
  - 创建 `frontend/` 与 `backend/` 两个产品目录，明确各自独立依赖、独立启动命令、独立 Dockerfile。
  - 在根目录声明全栈环境变量约定、服务端口约定、容器网络约定。
  - 在文档中明确“当前 workspace 作为统筹容器，前后端代码边界独立”的开发约束。
- Must preserve:
  - 不引入任何具体 AI 工具实现。
  - 不在本阶段引入认证、SSR、CI/CD。
- Validation:
  - 目录结构与文档能支持后续 `docker-compose up` 和非 Docker 双端启动说明。
- Completion evidence:
  - 根目录出现前后端目录、compose 文件、环境变量示例与开发说明。

### T-2 — Frontend SPA Scaffold, Navigation, And Proxy

- Purpose: 搭建 React + Vite + TypeScript 前端骨架，包含工具导航布局、空白工具页模板，以及同时代理 HTTP API 与 WebSocket 的开发服务器配置。
- Files or symbols:
  - `frontend/package.json`
  - `frontend/vite.config.ts`
  - `frontend/src/main.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/routes/`
  - `frontend/src/pages/tools/BlankToolPage.tsx`
  - `frontend/src/pages/tools/ChatToolPage.tsx`
  - `frontend/src/components/layout/`
  - `frontend/src/lib/api.ts`
  - `frontend/src/lib/ws.ts`
- Required change:
  - 初始化 Vite React TS 项目。
  - 使用路由与基础布局实现“工具导航页 -> 工具详情页”的信息架构。
  - 提供一个空白工具页模板：提交表单后请求后端 REST 示例接口并渲染响应。
  - 提供一个聊天页模板：建立 WebSocket 连接、展示消息流、支持断线自动重连。
  - 在 `vite.config.ts` 中配置 `/api` 的 HTTP 代理，以及 `/ws` 的 WebSocket 代理；如 SSE 路径独立，则一并代理 `/sse` 或 `/api/stream`。
- Must preserve:
  - 保持 SPA，不引入 SSR。
  - 工具页面只保留模板和联调示例，不实现真实 AI 逻辑。
- Validation:
  - `npm run dev` 下，前端无需改 CORS 配置即可访问后端 REST、WebSocket。
  - 空白工具页与聊天页都能从统一导航进入。
- Completion evidence:
  - 前端页面可见导航、空白工具页与聊天页模板；代理配置明确包含 HTTP 与 WebSocket。

### T-3 — Frontend Real-Time UX Template

- Purpose: 为后续实时类工具提供统一的聊天/流式交互前端基线，避免每个工具重复搭建连接管理和消息展示逻辑。
- Files or symbols:
  - `frontend/src/hooks/`
  - `frontend/src/components/chat/`
  - `frontend/src/types/`
  - `frontend/src/lib/ws.ts`
- Required change:
  - 提供消息列表、输入框、连接状态、自动重连和基础错误展示的通用组件/Hook。
  - 约定 WebSocket 消息 envelope 的前端类型定义。
  - 为 SSE 预留客户端订阅入口，至少在接口层可用。
- Must preserve:
  - 不把抽象做成框架；仅覆盖当前 intent 需要的请求-响应与实时聊天模板。
- Validation:
  - 聊天模板能完成连接、发送、接收、断线重连的基础链路。
- Completion evidence:
  - 前端实时模板可以复用到后续工具页面，而不是耦合在单一页面实现里。

### T-4 — FastAPI API, WebSocket, And SSE Skeleton

- Purpose: 建立 Python + FastAPI 后端骨架，打通 REST、WebSocket、SSE 三条通信路径，并提供结构化错误返回。
- Files or symbols:
  - `backend/pyproject.toml`
  - `backend/app/main.py`
  - `backend/app/api/`
  - `backend/app/ws/`
  - `backend/app/sse/`
  - `backend/app/core/config.py`
  - `backend/app/schemas/`
- Required change:
  - 初始化 FastAPI 项目与依赖管理。
  - 提供基础健康检查、工具列表、空白工具 REST 示例接口。
  - 提供聊天演示 WebSocket handler skeleton，至少支持 connect / receive / send / disconnect。
  - 提供 SSE skeleton，用于服务器单向事件流示例。
  - 约定统一响应 envelope 与错误结构，便于前端稳定消费。
- Must preserve:
  - 不实现真实 AI API 调用，只返回可验证的 mock/placeholder 数据。
- Validation:
  - REST、WebSocket、SSE 三条路由都可从开发环境访问。
- Completion evidence:
  - 后端启动后，前端空白页和聊天页可分别联通 REST 与 WebSocket；SSE 可被手工或测试脚本订阅。

### T-5 — Tool Registry Pattern And Minimal Module Contract

- Purpose: 设计“新增一个工具模块只需最少样板代码”的后端扩展机制，并让前端导航可消费同一份工具清单。
- Files or symbols:
  - `backend/app/tools/registry.py`
  - `backend/app/tools/base.py`
  - `backend/app/tools/modules/blank_tool.py`
  - `backend/app/tools/modules/chat_tool.py`
  - `backend/app/api/routes/tools.py`
- Required change:
  - 定义工具元数据结构：`tool_id`、`name`、`mode`、`route`、`capabilities` 等。
  - 定义最小模块约定：每个工具模块导出 metadata 与注册入口，按约定接入 REST / WebSocket / SSE 能力。
  - 后端通过注册表暴露工具列表接口，供前端导航动态渲染或初始化时消费。
  - 用两个示例模块验证模式：一个请求-响应型空白工具，一个聊天型工具模板。
- Must preserve:
  - 模块契约应简单、显式，不为未实现的未来工具做过度抽象。
- Validation:
  - 新增一个示例工具时，只需复制模块模板并完成约定字段，即可出现在工具列表并被路由访问。
- Completion evidence:
  - 形成一条可记录的“新增工具模块”最小流程，用于满足 AC-3。

### T-6 — PostgreSQL And Redis Foundation

- Purpose: 为聊天历史、工具调用记录、缓存与会话元数据提供基础存储能力。
- Files or symbols:
  - `backend/app/db/`
  - `backend/alembic.ini`
  - `backend/alembic/`
  - `backend/app/models/`
  - `backend/app/services/chat_history.py`
  - `backend/app/services/cache.py`
- Required change:
  - 选择并初始化数据库访问层与迁移工具。
  - 定义基础 schema：聊天会话表、聊天消息表、工具调用记录表。
  - 定义 Redis 连接与服务层，用于连接会话、短期缓存、可恢复元数据。
  - 在聊天 WebSocket 示例链路中接入最小历史持久化读写。
- Must preserve:
  - 仅建立当前 intent 要求的数据基础，不引入用户体系相关表。
- Validation:
  - 执行 migration 后，数据库中存在核心表。
  - 聊天历史在服务重启后仍可读取。
  - Redis 可用于缓存/会话元数据读写。
- Completion evidence:
  - PostgreSQL 与 Redis 都被真实接入到后端 skeleton，而非只在 compose 中占位。

### T-7 — Dockerized Full-Stack Development Experience

- Purpose: 提供一键启动的容器化开发体验，并同时保留本机非 Docker 调试路径。
- Files or symbols:
  - `frontend/Dockerfile`
  - `backend/Dockerfile`
  - `docker-compose.yml`
  - `docs/development.md`
  - `frontend/.env.example`
  - `backend/.env.example`
- Required change:
  - 为前端和后端分别编写开发向 Dockerfile。
  - 在 `docker-compose.yml` 中编排 frontend、backend、postgres、redis。
  - 配置代码挂载、端口暴露、依赖等待、数据库初始化所需环境变量。
  - 在文档中写清楚两套启动方式：`docker-compose up` 全栈模式，以及前后端分别本机运行的非 Docker 模式。
- Must preserve:
  - 不引入生产级反向代理或额外基础设施，除非为当前骨架运行所必需。
- Validation:
  - 容器模式能一键启动四个服务。
  - 非 Docker 模式能依赖同一份环境变量说明独立启动前端和后端。
- Completion evidence:
  - 新开发者只需按文档执行即可跑起完整 scaffold。

### T-8 — Verification Matrix And Acceptance Smoke Checks

- Purpose: 把 AC-1 到 AC-6 转成可执行的验证步骤，确保 scaffold 不是“只生成文件”，而是能实际跑通关键链路。
- Files or symbols:
  - `docs/development.md`
  - `frontend/`
  - `backend/`
  - `docker-compose.yml`
- Required change:
  - 为前端定义至少一条构建或静态检查命令。
  - 为后端定义至少一条测试或静态检查命令。
  - 编写手工 smoke checklist，覆盖：
    - 空白工具页调用 REST 成功
    - 聊天页 WebSocket 收发成功
    - 新增示例工具模块流程成立
    - PostgreSQL 持久化重启后保留数据
    - `docker-compose up` 成功
    - 非 Docker 开发代理同时覆盖 HTTP 和 WebSocket
- Must preserve:
  - 验证以当前架构骨架为中心，不扩展到未实现的具体 AI 能力。
- Validation:
  - 所有 acceptance checks 都能对应到明确命令或明确人工检查步骤。
- Completion evidence:
  - 执行阶段可以直接逐项对照 AC 与 smoke checklist 验收。

## Change Paths

Use exact repository-relative paths or directory prefixes.
Wildcards, absolute paths, and `..` are forbidden.

```paths
frontend/
backend/
docker-compose.yml
.env.example
docs/
```

## Tests and Quality Gates

```text
cd frontend && npm install && npm run build
cd frontend && npm run lint
cd backend && python -m pip install -r requirements-dev.txt
cd backend && pytest
cd backend && ruff check .
cd backend && alembic upgrade head
docker-compose up --build
curl http://localhost:8000/api/health
手工验证：前端空白工具页 REST 联调成功
手工验证：前端聊天页 WebSocket 收发与断线重连成功
手工验证：停止并重启容器后，聊天历史仍可读取
手工验证：非 Docker 模式下 Vite 代理同时覆盖 HTTP API 与 WebSocket
```

## Risks and Stop Conditions

- 若执行阶段发现“前后端分仓库”必须立即落成两个真正独立的 git 仓库，而当前 workspace 不允许这种目录/仓库布局，需要先确认仓库创建位置与交付方式，再继续执行。
- 若 `Vite dev proxy + FastAPI WebSocket` 在本项目端口与路径约定下无法稳定代理，需要先用最小样例验证路径前缀和 `ws: true` 配置，再继续扩展页面骨架。
- 若 PostgreSQL migration 方案与选定 ORM/driver 在 Windows 本机开发下不稳定，应先锁定最简单、可复现的组合，避免在骨架阶段引入替代方案分支。
- 若 Docker 在 Windows 开发环境中出现卷挂载或热更新异常，应优先保证“能启动并可联调”的基线，再把热更新优化列为后续改进，而不是扩张当前 scope。

## Approval

- Plan status: `APPROVED`
- Human approved the implementation plan in Codex conversation on `2026-07-24`.

## Handoff

### Workflow

- Workflow ID: `WF-20260725-ai-toolsite-arch-82F8`
- State version: `5`
- Completed role: `CODEX_PLANNING`
- Current stage: `CLAUDE_EXECUTION`
- Next role: `CLAUDE_EXECUTION`
- Branch: `agent/wf-20260725-ai-toolsite-arch-82f8`
- HEAD: `33bf622`

### Completed

- Verified workflow identity, state version, approved intent, branch correctness, and context freshness.
- Produced a complete implementation plan for frontend scaffold, backend scaffold, data foundation, Redis, Docker, developer experience, and acceptance validation.
- Mapped AC-1 through AC-6 to explicit ordered tasks and validation steps without redefining product intent.
- Recorded explicit Human plan approval and transitioned the Workflow to execution readiness.

### Files produced or updated

- `.agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8/30-plan.md`
- `.agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8/WORKFLOW.md`

### Validation

- `python .agent-workspace/validators/validate_workflow.py --workflow WF-20260725-ai-toolsite-arch-82F8` — PASS
- Residual risk: `前后端“独立 git 仓库”的最终落地方式需在执行前按实际交付位置确认`

### Human action

1. 将下面的 Claude Executor Prompt 粘贴到一个全新的 Claude 会话中执行。

### Copy-Paste Prompt for the Next Agent

```text
WORKFLOW_ID: WF-20260725-ai-toolsite-arch-82F8
EXPECTED_STATE_VERSION: 5
ROLE: CLAUDE_EXECUTION
WORKFLOW_PATH: .agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8

Read:
- .agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8/WORKFLOW.md
- .agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8/10-context.md
- .agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8/20-intent.md
- .agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8/30-plan.md
- .agent-workspace/protocol/WORKFLOW_PROTOCOL.md
- .agent-workspace/protocol/HANDOFF_TEMPLATE.md
- .agent-workspace/protocol/CLAUDE_RULES.md
- CLAUDE.md
- AGENTS.md

Do:
- Verify the Workflow ID, expected state version, current branch, and that the plan is approved.
- Execute only the approved implementation plan in 30-plan.md.
- Scaffold the frontend, backend, PostgreSQL/Redis foundation, Docker setup, and development docs within the approved scope.
- Do not redefine product intent and do not expand scope beyond the approved plan.
- Run the planned validation commands and any necessary smoke checks you can perform locally.
- Write .agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8/40-execution.md with execution evidence, changed paths, validations, and any residual risks.
- Update WORKFLOW.md to record execution progress and transition to CLAUDE_REVIEW when execution is complete.
- Run the Validator yourself.
- Produce the exact Review Prompt for a fresh Claude review session.

Write:
- product code and config files required by the approved plan
- .agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8/40-execution.md
- .agent-workspace/workflows/WF-20260725-ai-toolsite-arch-82F8/WORKFLOW.md

Do not:
- read sibling Workflow artifacts;
- change files outside the allowed role and approved scope;
- rewrite the approved Intent or Plan;
- perform the final Review in the same session;
- rely only on previous chat memory.

Before finishing:
- update WORKFLOW.md;
- run the Validator yourself;
- create the next Handoff with this same structure.
```

### Expected next output

- A completed implementation matching the approved plan, plus `40-execution.md`, a passing validator result, and an exact Claude Review Prompt for a fresh review session.

### Stop conditions

- Workflow ID, state version, branch, or approved-plan status does not match repository reality.
- Repository reality has changed enough to invalidate the approved plan before execution starts.
- Execution would require scope beyond the approved Product Intent or approved Implementation Plan.
- A fresh Claude session for independent review is not used after execution completes.
