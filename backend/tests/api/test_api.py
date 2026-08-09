"""End-to-end API tests over the ASGI app (in-memory SQLite).

Rate limiting is disabled for most tests; a dedicated test re-enables it with
a low limit to exercise the 429 path deterministically.
"""

import pytest
import pytest_asyncio

from app.core import ratelimit
from app.core.config import settings


@pytest_asyncio.fixture(autouse=True)
async def _disable_rate_limit(monkeypatch):
    """Keep the shared in-memory limiter out of ordinary tests."""
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    yield


@pytest.mark.asyncio
async def test_health(api_client):
    res = await api_client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_hello(api_client):
    res = await api_client.get("/api/hello")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["message"]


@pytest.mark.asyncio
async def test_config(api_client):
    res = await api_client.get("/api/config")
    body = res.json()
    assert body["success"] is True
    models = body["data"]["deepseek_models"]
    assert isinstance(models, list) and models
    assert body["data"]["deepseek_default_model"] in models


@pytest.mark.asyncio
async def test_tools_list(api_client):
    res = await api_client.get("/api/tools")
    body = res.json()
    assert body["success"] is True
    tool_ids = {t["tool_id"] for t in body["data"]["tools"]}
    assert {
        "blank_tool",
        "chat_tool",
        "code_agent_flow_viz",
        "task_decomposer",
    } <= tool_ids

    # config metadata is advertised so the frontend never hardcodes models
    td = next(t for t in body["data"]["tools"] if t["tool_id"] == "task_decomposer")
    assert "models" in td["config"]
    assert "supported_actions" in td["config"]


@pytest.mark.asyncio
async def test_tool_not_found(api_client):
    res = await api_client.get("/api/tools/does_not_exist")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_invoke_blank_tool(api_client):
    res = await api_client.post(
        "/api/tools/blank_tool/invoke", json={"payload": {"input": "hi"}}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["echo"] == "hi"


@pytest.mark.asyncio
async def test_invoke_validation_error(api_client):
    res = await api_client.post(
        "/api/tools/blank_tool/invoke", json={"payload": {"input": "x" * 4001}}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_invoke_unknown_tool(api_client):
    res = await api_client.post("/api/tools/nope/invoke", json={"payload": {}})
    assert res.status_code == 200
    assert res.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_audit_endpoint_records_invoke(api_client):
    await api_client.post(
        "/api/tools/blank_tool/invoke", json={"payload": {"input": "audit me"}}
    )
    res = await api_client.get("/api/audit/tool-calls?tool_id=blank_tool")
    body = res.json()
    assert body["success"] is True
    assert body["data"]["total"] >= 1
    assert body["data"]["records"][0]["tool_id"] == "blank_tool"
    assert body["data"]["records"][0]["success"] is True


@pytest.mark.asyncio
async def test_chat_session_crud(api_client):
    # create
    res = await api_client.post(
        "/api/chat/sessions", json={"title": "My Chat", "tool_id": "chat_tool"}
    )
    body = res.json()
    assert body["success"] is True
    session_id = body["data"]["session"]["id"]
    assert body["data"]["session"]["title"] == "My Chat"

    # list
    res = await api_client.get("/api/chat/sessions")
    sessions = res.json()["data"]["sessions"]
    assert sessions[0]["id"] == session_id

    # get one
    res = await api_client.get(f"/api/chat/sessions/{session_id}")
    assert res.json()["data"]["session"]["tool_id"] == "chat_tool"

    # add + list messages
    res = await api_client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"content": "hello", "role": "user"},
    )
    assert res.json()["data"]["message"]["role"] == "user"
    res = await api_client.get(f"/api/chat/sessions/{session_id}/messages")
    messages = res.json()["data"]["messages"]
    assert len(messages) == 1
    assert messages[0]["content"] == "hello"

    # missing session -> NOT_FOUND
    res = await api_client.get("/api/chat/sessions/does-not-exist")
    assert res.json()["error"]["code"] == "NOT_FOUND"

    # delete -> gone
    res = await api_client.delete(f"/api/chat/sessions/{session_id}")
    assert res.json()["data"]["deleted"] is True
    res = await api_client.get(f"/api/chat/sessions/{session_id}")
    assert res.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_rate_limit_429(api_client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_per_minute", 3)
    monkeypatch.setattr(ratelimit, "_redis_ok", False)  # skip redis probe
    ratelimit._memory.clear()

    statuses = []
    for _ in range(4):
        res = await api_client.post(
            "/api/tools/blank_tool/invoke", json={"payload": {"input": "x"}}
        )
        statuses.append(res.status_code)

    assert statuses[:3] == [200, 200, 200]
    assert statuses[3] == 429
    assert res.json()["error"]["code"] == "RATE_LIMITED"
