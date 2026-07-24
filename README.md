# Claude–Codex Prompt-Native Workflow

一个基于 **Claude Code + Codex** 的轻量级软件开发协作流程。

```text
Claude: Project Reading + Intent
→ Codex: Planning
→ Human: Plan Approval
→ Claude: Execution
→ Claude: Independent Review
→ Human: Accept / Remediation
```

## 核心原则

- Prompt 约束 Agent 行为；
- Agent 自动维护文件、Git、测试和状态；
- Markdown 保存可恢复、可审计的 Workflow；
- Human 只在 Agent 对话中确认和决策；
- Validator 只检查，不编排流程；
- 所有 Workflow 串行执行。

## 角色

### Claude Code

负责：

- 创建 Workflow；
- 阅读项目；
- 与 Human 澄清并确认 Product Intent；
- 执行 Codex 制定且经 Human 批准的 Plan；
- 在新的 Claude 会话中独立 Review；
- 修复 Human 选中的 Review Finding。

执行与 Review 必须使用不同的 Claude 会话。Reviewer 不得直接修改产品代码。

### Codex

只负责：

- 根据已确认的 Intent 制定技术 Plan；
- 在 Human 批准后生成 Claude 执行 Handoff。

Codex 不负责执行或最终 Review。

### Human

只需在 Agent 对话中：

- 描述目标；
- 回答必要的产品问题；
- 确认 Intent；
- 批准 Plan；
- 选择需要修复的 Finding；
- 接受最终结果。

Human 不需要编辑 Workflow 文件或手动运行 Validator。

## 项目结构

```text
project-root/
├── README.md
├── CLAUDE.md
├── AGENTS.md
└── .agent-workspace/
    ├── protocol/
    ├── project/
    ├── templates/
    ├── workflows/
    └── validators/
```

每个目标对应一个独立 Workflow：

```text
.agent-workspace/workflows/<WORKFLOW_ID>/
├── WORKFLOW.md
├── 10-context.md
├── 20-intent.md
├── 30-plan.md
├── 40-execution.md
└── 50-review.md
```

## 使用流程

1. 在 Claude Code 中描述目标。
2. Claude 创建 Workflow、阅读项目，并与 Human 确认 Intent。
3. Claude 写入 `20-intent.md` 并生成 Codex Planning Prompt。
4. Codex 制定 `30-plan.md`，Human 在 Codex 对话中批准。
5. Claude 执行 Plan 并写入 `40-execution.md`。
6. 在新的 Claude 会话中完成独立 Review，并写入 `50-review.md`。
7. Human 接受结果，或选择需要修复的 Finding ID。

详细说明见：

```text
.agent-workspace/QUICKSTART.md
.agent-workspace/protocol/WORKFLOW_PROTOCOL.md
```
