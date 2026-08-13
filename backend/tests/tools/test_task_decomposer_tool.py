"""Tests for the Task Decomposer plugin.

Operations are now named Pydantic handlers (``analyze_task`` / ``list_history`` /
``get_history`` / ``delete_history``) reached through the Host runtime. These
tests drive the handlers directly with a ``ToolContext`` and pin the typed-error
contract plus the input-model validation the Host performs before dispatch.
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.config import settings
from app.core.errors import NotFoundError, ProviderError, ValidationError
from app.services.llm import (
    ProviderError as LlmProviderError,
    resolve_api_key,
    resolve_provider,
)
from app.tool_host.contracts import ToolContext
from app.tool_plugins.task_decomposer.client import (
    AnalyzeTaskInput,
    ModelTaskAnalysis,
    TaskAnalysis,
    build_agent_prompt,
)
from app.tool_plugins.task_decomposer.plugin import (
    HistoryIdInput,
    ListHistoryInput,
    analyze_task,
    delete_history_item,
    get_history_item,
    list_history_items,
    plugin,
)
from app.tool_plugins.task_decomposer.repository import (
    count_history,
    create_history,
)

# The DeepSeek provider, resolved once for the key-resolution unit tests.
_DEEPSEEK = resolve_provider("deepseek-v4-flash")


def test_manifest_metadata():
    manifest = plugin.manifest()
    assert manifest.id == "task_decomposer"
    assert manifest.name == "Task Decomposer"
    ids = [op.id for op in manifest.operations]
    assert ids == ["analyze_task", "list_history", "get_history", "delete_history"]
    assert manifest.ui.kind.value == "custom"
    assert manifest.ui.layout.value == "fullscreen"


# ── Input-model validation (performed by the Host before dispatch) ──


def test_analyze_task_missing_raw_task():
    with pytest.raises(PydanticValidationError):
        AnalyzeTaskInput.model_validate({"model": "deepseek-v4-flash"})


def test_analyze_task_with_empty_task():
    with pytest.raises(PydanticValidationError):
        AnalyzeTaskInput.model_validate({"raw_task": "", "model": "deepseek-v4-flash"})


def test_analyze_task_oversized_risk_hint_rejected():
    """A single risk hint over the 200-char cap is rejected before any API call."""
    with pytest.raises(PydanticValidationError):
        AnalyzeTaskInput.model_validate(
            {
                "raw_task": "task",
                "model": "deepseek-v4-flash",
                "risk_hints": ["x" * 300],
            }
        )


# ── Handler behaviour ──


@pytest.mark.asyncio
async def test_analyze_task_unsupported_model(db):
    with pytest.raises(ValidationError) as excinfo:
        await analyze_task(
            AnalyzeTaskInput(raw_task="task", model="gpt-4o"), ToolContext(db=db)
        )
    assert excinfo.value.code == "VALIDATION_ERROR"
    assert "不支持" in str(excinfo.value)


@pytest.mark.asyncio
async def test_analyze_task_coerces_numeric_raw_task(db, monkeypatch):
    """A numeric raw_task is coerced to a string instead of 500ing."""
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-x")
    monkeypatch.setattr(
        "app.tool_plugins.task_decomposer.plugin.analyze_with_llm", _fake_analyze
    )
    result = await analyze_task(
        AnalyzeTaskInput(raw_task="12345", model="deepseek-v4-flash"),
        ToolContext(db=db),
    )
    assert result.analysis.goal == "fake"
    assert result.model == "deepseek-v4-flash"


async def _fake_analyze(input_data):
    """Stands in for analyze_with_llm so the test needs no network."""
    return TaskAnalysis(
        goal="fake",
        context=["c"],
        constraints=["c"],
        done_when=["d"],
        failure_cases=["f"],
        verification=["v"],
        missing_questions=[],
        risk_level="low",
        non_goals=[],
        agent_prompt="p",
    )


@pytest.mark.asyncio
async def test_analyze_task_no_api_key(db, monkeypatch):
    """Without .env key or session key, the client error surfaces as ProviderError."""
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    with pytest.raises(ProviderError) as excinfo:
        await analyze_task(
            AnalyzeTaskInput(
                raw_task="test task",
                context="",
                task_type="feature",
                risk_hints=[],
                model="deepseek-v4-flash",
                session_api_key="",
            ),
            ToolContext(db=db),
        )
    assert excinfo.value.code == "LLM_ERROR"


@pytest.mark.asyncio
async def test_analyze_task_prunes_history(db, monkeypatch):
    """History retention runs on analyze so the table stays bounded."""
    monkeypatch.setattr(settings, "task_decomposer_history_max_records", 3)
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-x")
    monkeypatch.setattr(
        "app.tool_plugins.task_decomposer.plugin.analyze_with_llm", _fake_analyze
    )

    for i in range(3):
        await create_history(
            db,
            raw_task=f"seed {i}",
            context="",
            task_type="feature",
            model_name="m",
            risk_hints=None,
            risk_level="low",
            structured_output={"goal": "g"},
        )
    await db.commit()
    assert await count_history(db) == 3

    await analyze_task(
        AnalyzeTaskInput(raw_task="new task", model="deepseek-v4-flash"),
        ToolContext(db=db),
    )
    await db.commit()

    # The new insert + prune keeps history at the cap, not at cap + 1.
    assert await count_history(db) == 3


@pytest.mark.asyncio
async def test_list_history_empty(db):
    result = await list_history_items(ListHistoryInput(), ToolContext(db=db))
    assert result.records == []


@pytest.mark.asyncio
async def test_list_history_returns_saved_records(db):
    await create_history(
        db,
        raw_task="Fix bug",
        context="",
        task_type="bugfix",
        model_name="deepseek-v4-flash",
        risk_hints=None,
        risk_level="high",
        structured_output={"goal": "fix"},
    )
    await db.commit()
    result = await list_history_items(
        ListHistoryInput(task_type="bugfix"), ToolContext(db=db)
    )
    assert len(result.records) == 1
    assert result.records[0].raw_task == "Fix bug"
    assert result.records[0].risk_level == "high"


@pytest.mark.asyncio
async def test_get_history_not_found(db):
    with pytest.raises(NotFoundError):
        await get_history_item(HistoryIdInput(id="missing"), ToolContext(db=db))


@pytest.mark.asyncio
async def test_delete_history_not_found(db):
    with pytest.raises(NotFoundError):
        await delete_history_item(HistoryIdInput(id="missing"), ToolContext(db=db))


# ── Model client unit tests (moved with the plugin) ──


def test_build_agent_prompt_includes_sections():
    analysis = ModelTaskAnalysis(
        goal="实现安全导入",
        context=["背景1", "背景2"],
        constraints=["限制1"],
        done_when=["标准1"],
        failure_cases=["失败1"],
        verification=["验证1"],
        risk_level="medium",
    )
    prompt = build_agent_prompt(analysis)
    assert "# Goal" in prompt
    assert "实现安全导入" in prompt
    assert "# Context" in prompt
    assert "- 背景1" in prompt
    assert "# Constraints" in prompt
    assert "# Done when" in prompt
    assert "# Failure cases" in prompt
    assert "# Verification" in prompt
    assert "# Missing questions" in prompt
    assert "# Non-goals" in prompt
    assert prompt.startswith("先不要直接写代码。")


def test_build_agent_prompt_with_empty_lists():
    analysis = ModelTaskAnalysis(
        goal="test",
        context=["ctx"],
        constraints=["c"],
        done_when=["d"],
        failure_cases=["f"],
        verification=["v"],
        missing_questions=[],
        non_goals=[],
        risk_level="low",
    )
    prompt = build_agent_prompt(analysis)
    assert "- 暂无" in prompt  # fallback for empty lists


def test_resolve_api_key_prefers_settings(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "env-key")
    result = resolve_api_key(_DEEPSEEK, session_api_key="sk-session-key")
    assert result == "env-key"


def test_resolve_api_key_fallback(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    result = resolve_api_key(_DEEPSEEK, session_api_key="sk-session-key")
    assert result == "sk-session-key"


def test_resolve_api_key_rejects_bad_session_key(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    with pytest.raises(LlmProviderError, match="sk-"):
        resolve_api_key(_DEEPSEEK, session_api_key="not-a-key")


def test_resolve_api_key_raises_when_both_missing(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    with pytest.raises(LlmProviderError, match="未配置"):
        resolve_api_key(_DEEPSEEK, session_api_key="")
