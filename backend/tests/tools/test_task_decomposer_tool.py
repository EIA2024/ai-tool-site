"""Tests for the Task Decomposer tool module."""

import pytest

from app.tools.modules.task_decomposer import (
    TaskDecomposerTool,
    _analysis_to_dict,
    _history_to_dict,
)
from app.tools.modules.task_decomposer_client import (
    ModelTaskAnalysis,
    _resolve_api_key,
    build_agent_prompt,
)

tool = TaskDecomposerTool()


def test_tool_id_and_metadata():
    assert tool.tool_id == "task_decomposer"
    assert tool.name == "Task Decomposer"
    assert tool.mode == "request-response"


@pytest.mark.asyncio
async def test_unknown_action():
    result = await tool.handle_invoke({"action": "bogus"})
    assert result["success"] is False
    assert result["error"]["code"] == "UNKNOWN_ACTION"


@pytest.mark.asyncio
async def test_analyze_task_missing_raw_task():
    result = await tool.handle_invoke({"action": "analyze_task"})
    assert result["success"] is False
    assert result["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_analyze_task_with_empty_task():
    result = await tool.handle_invoke({"action": "analyze_task", "raw_task": ""})
    assert result["success"] is False
    assert result["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_list_history_no_records():
    result = await tool.handle_invoke({"action": "list_history"})
    # Without a real PostgreSQL connection, this may return an INTERNAL_ERROR
    # or succeed with empty list (if a test DB is configured).
    # Accept both outcomes — the important thing is it doesn't crash.
    if result["success"]:
        assert result["data"]["records"] == []
    else:
        assert result["error"]["code"] in ("INTERNAL_ERROR",)


@pytest.mark.asyncio
async def test_analyze_task_no_api_key():
    """Without .env key or session key, should return DEEPSEEK_ERROR."""
    result = await tool.handle_invoke({
        "action": "analyze_task",
        "raw_task": "test task",
        "context": "",
        "task_type": "feature",
        "risk_hints": [],
        "model": "deepseek-v4-flash",
        "session_api_key": "",
    })
    assert result["success"] is False
    assert result["error"]["code"] == "DEEPSEEK_ERROR"


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


# ── F-003: DeepSeek client unit tests ──


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
    """_resolve_api_key should prefer settings.deepseek_api_key over session key."""
    monkeypatch.setattr("app.tools.modules.task_decomposer_client.settings.deepseek_api_key", "env-key")
    from app.tools.modules.task_decomposer_client import AnalyzeTaskInput
    result = _resolve_api_key(AnalyzeTaskInput(raw_task="t", session_api_key="session-key"))
    assert result == "env-key"


def test_resolve_api_key_fallback(monkeypatch):
    """_resolve_api_key should fall back to session key when env key is empty."""
    monkeypatch.setattr("app.tools.modules.task_decomposer_client.settings.deepseek_api_key", "")
    from app.tools.modules.task_decomposer_client import AnalyzeTaskInput
    result = _resolve_api_key(AnalyzeTaskInput(raw_task="t", session_api_key="session-key"))
    assert result == "session-key"


def test_resolve_api_key_raises_when_both_missing(monkeypatch):
    """_resolve_api_key should raise when both keys are absent."""
    monkeypatch.setattr("app.tools.modules.task_decomposer_client.settings.deepseek_api_key", "")
    from app.tools.modules.task_decomposer_client import DeepSeekClientError, AnalyzeTaskInput
    with pytest.raises(DeepSeekClientError, match="未配置"):
        _resolve_api_key(AnalyzeTaskInput(raw_task="t"))
