"""Model integration for the Task Decomposer tool.

Handles prompt construction, JSON validation, deterministic agent_prompt
generation, and a bounded retry for the model's non-deterministic JSON.
The raw HTTP call lives in the shared ``app.services.llm`` client.
"""

import json
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.services.llm import ProviderError, chat_completion

# Each risk hint is short; the per-item cap keeps the prompt (and thus the
# model spend) bounded even if a client sends many verbose hints.
_RISK_HINT = Annotated[str, StringConstraints(max_length=200)]


# ── Internal schemas (not exposed outside this tool) ──


class AnalyzeTaskInput(BaseModel):
    raw_task: str = Field(min_length=1, max_length=4000)
    context: str = Field(default="", max_length=4000)
    task_type: str = Field(default="feature", max_length=20)
    risk_hints: list[_RISK_HINT] = Field(default_factory=list, max_length=12)
    model: str = Field(min_length=1, max_length=64)
    session_api_key: str = Field(default="", max_length=256)


class ModelTaskAnalysis(BaseModel):
    goal: str = Field(min_length=1)
    context: list[str] = Field(min_length=1)
    constraints: list[str] = Field(min_length=1)
    done_when: list[str] = Field(min_length=1)
    failure_cases: list[str] = Field(min_length=1)
    verification: list[str] = Field(min_length=1)
    missing_questions: list[str] = Field(default_factory=list)
    risk_level: str = Field(pattern=r"^(low|medium|high)$")
    non_goals: list[str] = Field(default_factory=list)


class TaskAnalysis(ModelTaskAnalysis):
    agent_prompt: str = Field(min_length=1)


# ── Prompt building ──


def build_system_prompt() -> str:
    return (
        "你是一个严谨的工程任务拆解助手，帮助即将进入企业实习的程序员"
        "把模糊需求拆成 Coding Agent 可执行任务卡。\n\n"
        "你必须输出 json，且只能输出一个 JSON object。"
        "不要输出 Markdown，不要解释，不要包含代码块。\n\n"
        '输出 JSON 格式示例：\n'
        '{\n'
        '  "goal": "一句话说明本轮要交付的业务或工程结果",\n'
        '  "context": ["从用户输入中提取的背景", "需要先调查的上下文"],\n'
        '  "constraints": ["必须遵守的边界", "不能做的范围"],\n'
        '  "done_when": ["可验证完成标准"],\n'
        '  "failure_cases": ["必须处理或验证的失败路径"],\n'
        '  "verification": ["需要运行的检查或手工验证"],\n'
        '  "missing_questions": ["仍需向需求方确认的问题"],\n'
        '  "risk_level": "low",\n'
        '  "non_goals": ["本轮明确不做的内容"]\n'
        '}\n\n'
        "规则：\n"
        "- 不要直接复制用户原始任务作为 goal，要抽象成可交付结果。\n"
        "- 必须根据任务类型和风险提示生成具体 constraints、failure_cases 和 verification。\n"
        "- 如果信息不足，把不确定点放入 missing_questions，不要编造仓库事实。\n"
        "- risk_level 只能是 low、medium、high。\n"
        "- 不要输出 agent_prompt 字段；后端会用你输出的结构化字段生成最终 Prompt。"
    )


def build_user_prompt(input_data: AnalyzeTaskInput) -> str:
    return json.dumps(
        {
            "raw_task": input_data.raw_task,
            "context": input_data.context,
            "task_type": input_data.task_type,
            "risk_hints": input_data.risk_hints,
            "expected_language": "zh-CN",
            "instruction": "请分析这个开发任务，输出严格 JSON object。",
        },
        ensure_ascii=False,
    )


# ── Agent prompt generation (deterministic, not from model) ──


def _markdown_list(items: list[str]) -> str:
    if not items:
        return "- 暂无"
    return "\n".join(f"- {item}" for item in items)


def build_agent_prompt(analysis: ModelTaskAnalysis) -> str:
    missing_questions = analysis.missing_questions or ["暂无"]
    non_goals = analysis.non_goals or ["暂无"]
    return "\n".join(
        [
            "先不要直接写代码。",
            "",
            "请先按下面的任务卡进行只读调查，然后输出最小修改计划。"
            "只有在计划被确认后再实现。",
            "",
            "# Goal",
            analysis.goal,
            "",
            "# Context",
            _markdown_list(analysis.context),
            "",
            "# Constraints",
            _markdown_list(analysis.constraints),
            "",
            "# Done when",
            _markdown_list(analysis.done_when),
            "",
            "# Failure cases",
            _markdown_list(analysis.failure_cases),
            "",
            "# Verification",
            _markdown_list(analysis.verification),
            "",
            "# Missing questions",
            _markdown_list(missing_questions),
            "",
            "# Non-goals",
            _markdown_list(non_goals),
            "",
            "请输出：",
            "1. 只读调查证据；",
            "2. 修改文件列表；",
            "3. 正常路径和失败路径；",
            "4. 验证计划；",
            "5. 需要我确认的问题。",
        ]
    )


# ── Model API call ──


async def _call_once(input_data: AnalyzeTaskInput) -> ModelTaskAnalysis:
    """Run a single completion and parse the model's JSON into the schema.

    The HTTP call itself lives in the shared model client; this function only
    attaches the tool's prompt and validates the model's JSON against the
    task-card schema. Raises ``ProviderError`` on any failure.
    """
    content = await chat_completion(
        [
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": build_user_prompt(input_data)},
        ],
        input_data.model,
        api_key=input_data.session_api_key,
        max_tokens=2200,
        temperature=0.2,
        response_format={"type": "json_object"},
        timeout=60,
    )

    try:
        return ModelTaskAnalysis.model_validate(json.loads(content))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ProviderError(
            "模型返回的 JSON 未通过 schema 校验", retryable=True
        ) from exc


async def analyze_with_llm(input_data: AnalyzeTaskInput) -> TaskAnalysis:
    # LLM JSON output is non-deterministic: one call in a few returns
    # truncated or schema-invalid JSON even with response_format. Retry
    # retryable failures (parse errors, transient transport/5xx) with a
    # fresh completion rather than failing the user on a bad roll. 4xx
    # auth/quota errors are never retried.
    last_error: ProviderError | None = None
    for _attempt in range(3):
        try:
            model_analysis = await _call_once(input_data)
        except ProviderError as exc:
            if not exc.retryable:
                raise
            last_error = exc
            continue
        return TaskAnalysis(
            **model_analysis.model_dump(),
            agent_prompt=build_agent_prompt(model_analysis),
        )
    # Only reachable when every attempt failed retryably.
    raise last_error or ProviderError("模型服务调用多次失败")
