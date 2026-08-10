"""Retry semantics for analyze_with_llm.

The model's JSON output is non-deterministic, so a single failed roll should
not fail the user. These tests pin the retry policy: retryable failures are
re-attempted with a fresh completion, non-retryable (4xx auth/quota) ones
surface immediately, and retries are bounded.
"""

import pytest

from app.services.llm import ProviderError
from app.tools.modules.task_decomposer_client import (
    AnalyzeTaskInput,
    ModelTaskAnalysis,
    analyze_with_llm,
)

_VALID_ANALYSIS = ModelTaskAnalysis(
    goal="goal",
    context=["ctx"],
    constraints=["c"],
    done_when=["done"],
    failure_cases=["fail"],
    verification=["verify"],
    risk_level="low",
)

_INPUT = AnalyzeTaskInput(
    raw_task="task",
    context="",
    task_type="feature",
    risk_hints=[],
    model="deepseek-v4-flash",
)


@pytest.mark.asyncio
async def test_retries_then_succeeds_on_bad_roll(monkeypatch):
    """One bad roll followed by a good one → success, exactly 2 attempts."""
    calls = []

    async def flaky(_input_data):
        calls.append(1)
        if len(calls) == 1:
            raise ProviderError(
                "模型返回的 JSON 未通过 schema 校验", retryable=True
            )
        return _VALID_ANALYSIS

    monkeypatch.setattr(
        "app.tools.modules.task_decomposer_client._call_once", flaky
    )
    result = await analyze_with_llm(_INPUT)
    assert result.goal == "goal"
    assert result.agent_prompt
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_non_retryable_failure_raises_immediately(monkeypatch):
    """4xx auth/quota errors must NOT be retried."""
    calls = []

    async def always_bad(_input_data):
        calls.append(1)
        raise ProviderError("模型服务返回错误：HTTP 401 Unauthorized")

    monkeypatch.setattr(
        "app.tools.modules.task_decomposer_client._call_once", always_bad
    )
    with pytest.raises(ProviderError, match="401"):
        await analyze_with_llm(_INPUT)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_retries_are_bounded_after_persistent_failure(monkeypatch):
    """All attempts retryable and failing → raise the last error, <=3 calls."""
    calls = []

    async def always_bad(_input_data):
        calls.append(1)
        raise ProviderError("无法连接模型服务", retryable=True)

    monkeypatch.setattr(
        "app.tools.modules.task_decomposer_client._call_once", always_bad
    )
    with pytest.raises(ProviderError, match="无法连接"):
        await analyze_with_llm(_INPUT)
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_5xx_is_retryable(monkeypatch):
    """Server-side errors carry retryable=True so the loop will retry them."""
    err = ProviderError(
        "模型服务返回错误：HTTP 503 Service Unavailable", retryable=True
    )
    calls = []

    async def fail_then_succeed(_input_data):
        calls.append(1)
        if len(calls) == 1:
            raise err
        return _VALID_ANALYSIS

    monkeypatch.setattr(
        "app.tools.modules.task_decomposer_client._call_once", fail_then_succeed
    )
    result = await analyze_with_llm(_INPUT)
    assert result.goal == "goal"
    assert len(calls) == 2
