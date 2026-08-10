"""Tests for the Task Decomposer tool module.

The refactor moved the tool onto the typed-error contract: ``handle_invoke``
takes ``(payload, db)``, returns the data payload only, and signals expected
failures by raising ``ValidationError`` / ``NotFoundError`` / ``ProviderError``.
"""

import pytest

from app.core.config import settings
from app.core.errors import NotFoundError, ProviderError, ValidationError
from app.services.llm import (
    ProviderError as LlmProviderError,
)
from app.services.llm import (
    resolve_api_key,
    resolve_provider,
)
from app.services.task_decomposer_history import create_history
from app.tools.modules.task_decomposer import (
    TaskDecomposerTool,
    _analysis_to_dict,
    _history_to_dict,
)
from app.tools.modules.task_decomposer_client import (
    ModelTaskAnalysis,
    build_agent_prompt,
)

tool = TaskDecomposerTool()

# The DeepSeek provider, resolved once for the key-resolution unit tests.
_DEEPSEEK = resolve_provider("deepseek-v4-flash")


def test_tool_id_and_metadata():
    assert tool.tool_id == "task_decomposer"
    assert tool.name == "Task Decomposer"
    assert tool.mode == "request-response"


def test_config_advertises_models_and_actions():
    cfg = tool.config()
    assert "analyze_task" in cfg["supported_actions"]
    assert isinstance(cfg["models"], list)
    assert cfg["default_model"] in cfg["models"]


@pytest.mark.asyncio
async def test_unknown_action(db):
    with pytest.raises(ValidationError) as excinfo:
        await tool.handle_invoke({"action": "bogus"}, db)
    assert excinfo.value.code == "VALIDATION_ERROR"
    assert "bogus" in str(excinfo.value)


@pytest.mark.asyncio
async def test_analyze_task_missing_raw_task(db):
    with pytest.raises(ValidationError) as excinfo:
        await tool.handle_invoke({"action": "analyze_task"}, db)
    assert excinfo.value.code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_analyze_task_with_empty_task(db):
    with pytest.raises(ValidationError):
        await tool.handle_invoke({"action": "analyze_task", "raw_task": ""}, db)


@pytest.mark.asyncio
async def test_analyze_task_unsupported_model(db):
    with pytest.raises(ValidationError) as excinfo:
        await tool.handle_invoke(
            {"action": "analyze_task", "raw_task": "task", "model": "gpt-4o"}, db
        )
    assert "不支持" in str(excinfo.value)


@pytest.mark.asyncio
async def test_analyze_task_oversized_risk_hint_rejected(db):
    """A single risk hint over the 200-char cap is rejected before any API call."""
    with pytest.raises(ValidationError) as excinfo:
        await tool.handle_invoke(
            {
                "action": "analyze_task",
                "raw_task": "task",
                "model": "deepseek-v4-flash",
                "risk_hints": ["x" * 300],
            },
            db,
        )
    assert excinfo.value.code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_analyze_task_coerces_numeric_raw_task(db, monkeypatch):
    """A numeric raw_task is coerced to a string instead of 500ing."""
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-x")
    monkeypatch.setattr(
        "app.tools.modules.task_decomposer.analyze_with_llm",
        _fake_analyze,
    )
    result = await tool.handle_invoke(
        {"action": "analyze_task", "raw_task": 12345, "model": "deepseek-v4-flash"},
        db,
    )
    assert result["analysis"]["goal"] == "fake"


async def _fake_analyze(input_data):
    """Stands in for analyze_with_llm so the test needs no network."""
    from app.tools.modules.task_decomposer_client import TaskAnalysis

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
        await tool.handle_invoke(
            {
                "action": "analyze_task",
                "raw_task": "test task",
                "context": "",
                "task_type": "feature",
                "risk_hints": [],
                "model": "deepseek-v4-flash",
                "session_api_key": "",
            },
            db,
        )
    assert excinfo.value.code == "LLM_ERROR"


@pytest.mark.asyncio
async def test_analyze_task_prunes_history(db, monkeypatch):
    """History retention runs on analyze so the table stays bounded."""
    from app.services.task_decomposer_history import count_history, create_history

    monkeypatch.setattr(settings, "task_decomposer_history_max_records", 3)
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-x")
    monkeypatch.setattr(
        "app.tools.modules.task_decomposer.analyze_with_llm", _fake_analyze
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

    await tool.handle_invoke(
        {"action": "analyze_task", "raw_task": "new task", "model": "deepseek-v4-flash"},
        db,
    )
    await db.commit()

    # The new insert + prune keeps history at the cap, not at cap + 1.
    assert await count_history(db) == 3


@pytest.mark.asyncio
async def test_list_history_empty(db):
    result = await tool.handle_invoke({"action": "list_history"}, db)
    assert result["records"] == []


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
    result = await tool.handle_invoke(
        {"action": "list_history", "task_type": "bugfix"}, db
    )
    assert len(result["records"]) == 1
    assert result["records"][0]["raw_task"] == "Fix bug"
    assert result["records"][0]["risk_level"] == "high"


@pytest.mark.asyncio
async def test_get_history_not_found(db):
    with pytest.raises(NotFoundError):
        await tool.handle_invoke({"action": "get_history", "id": "missing"}, db)


@pytest.mark.asyncio
async def test_delete_history_not_found(db):
    with pytest.raises(NotFoundError):
        await tool.handle_invoke({"action": "delete_history", "id": "missing"}, db)


def test_analysis_to_dict():
    class MockAnalysis:
        goal = "test"
        context = ["ctx"]
        constraints = ["c"]
        done_when = ["d"]
        failure_cases = ["f"]
        verification = ["v"]
        missing_questions = []
        risk_level = "low"
        non_goals = []
        agent_prompt = "prompt"

    d = _analysis_to_dict(MockAnalysis())
    assert d["goal"] == "test"
    assert d["agent_prompt"] == "prompt"
    assert d["risk_level"] == "low"


def test_history_to_dict():
    class MockRecord:
        id = "abc-123"
        raw_task = "task"
        context = "ctx"
        task_type = "feature"
        model_name = "deepseek-v4-flash"
        risk_hints = ["data_loss"]
        risk_level = "medium"
        structured_output = {"goal": "g"}
        created_at = None

    d = _history_to_dict(MockRecord())
    assert d["id"] == "abc-123"
    assert d["task_type"] == "feature"
    assert d["risk_level"] == "medium"


# ── Model client unit tests ──


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
    """The shared client prefers settings.deepseek_api_key over a session key."""
    monkeypatch.setattr(settings, "deepseek_api_key", "env-key")
    result = resolve_api_key(_DEEPSEEK, session_api_key="sk-session-key")
    assert result == "env-key"


def test_resolve_api_key_fallback(monkeypatch):
    """The shared client falls back to a valid session key when env key is empty."""
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    result = resolve_api_key(_DEEPSEEK, session_api_key="sk-session-key")
    assert result == "sk-session-key"


def test_resolve_api_key_rejects_bad_session_key(monkeypatch):
    """A session key not starting with 'sk-' must be rejected."""
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    with pytest.raises(LlmProviderError, match="sk-"):
        resolve_api_key(_DEEPSEEK, session_api_key="not-a-key")


def test_resolve_api_key_raises_when_both_missing(monkeypatch):
    """The shared client raises when both keys are absent."""
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    with pytest.raises(LlmProviderError, match="未配置"):
        resolve_api_key(_DEEPSEEK, session_api_key="")
