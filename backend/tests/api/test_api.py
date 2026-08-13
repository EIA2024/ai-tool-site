"""End-to-end API tests over the ASGI app (in-memory SQLite).

Rate limiting is disabled for most tests; a dedicated test re-enables it with
a low limit to exercise the 429 path deterministically.
"""

from types import SimpleNamespace

import pytest
import pytest_asyncio

from app.core import ratelimit
from app.core.config import settings
from app.tool_host.gateway import client_ip


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
    models = body["data"]["models"]
    assert isinstance(models, list) and models
    assert body["data"]["default_model"] in models


@pytest.mark.asyncio
async def test_tools_list(api_client):
    """The Dock sees only the three public tools; the Blank example is hidden."""
    res = await api_client.get("/api/tools")
    body = res.json()
    assert body["success"] is True
    tool_ids = {t["id"] for t in body["data"]["tools"]}
    assert tool_ids == {"chat_tool", "code_agent_flow_viz", "task_decomposer"}
    assert "blank_tool" not in tool_ids

    # Manifests advertise operations (input/output JSON Schema) so the frontend
    # never hardcodes the operation vocabulary.
    chat = next(t for t in body["data"]["tools"] if t["id"] == "chat_tool")
    operation_ids = {op["id"] for op in chat["operations"]}
    assert "send_message" in operation_ids
    assert "list_sessions" in operation_ids


@pytest.mark.asyncio
async def test_get_tool_includes_hidden(api_client):
    """Direct access still resolves the hidden Blank tool (schema-rendered)."""
    res = await api_client.get("/api/tools/blank_tool")
    body = res.json()
    assert body["success"] is True
    tool = body["data"]["tool"]
    assert tool["id"] == "blank_tool"
    assert tool["ui"]["kind"] == "schema"


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
        "/api/tools/blank_tool/operations/echo", json={"payload": {"input": "hi"}}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["echo"] == "hi"


@pytest.mark.asyncio
async def test_invoke_validation_error(api_client):
    res = await api_client.post(
        "/api/tools/blank_tool/operations/echo",
        json={"payload": {"input": "x" * 4001}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_invoke_unknown_tool(api_client):
    res = await api_client.post(
        "/api/tools/nope/operations/echo", json={"payload": {}}
    )
    assert res.status_code == 200
    assert res.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_invoke_unknown_operation(api_client):
    res = await api_client.post(
        "/api/tools/blank_tool/operations/nope", json={"payload": {}}
    )
    assert res.status_code == 200
    assert res.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_realtime_operation_over_http_rejected(api_client):
    """A realtime operation must be reached over WebSocket, not the REST path."""
    res = await api_client.post(
        "/api/tools/chat_tool/operations/send_message",
        json={"payload": {"content": "hi"}},
    )
    assert res.status_code == 200
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_invoke_import_records_batch(api_client):
    """A batch import is one invoke (one rate-limit slot) and dedups in-place."""
    res = await api_client.post(
        "/api/tools/code_agent_flow_viz/operations/import_records",
        json={
            "payload": {
                "records": [
                    {
                        "stage_key": "s1",
                        "user_input": "a",
                        "agent_output": "b",
                        "feedback": "c",
                        "next_steps": "d",
                    },
                    {
                        "stage_key": "s1",
                        "user_input": "a",
                        "agent_output": "b",
                        "feedback": "c",
                        "next_steps": "d",
                    },  # duplicate
                    {
                        "stage_key": "s2",
                        "user_input": "x",
                        "agent_output": "y",
                        "feedback": "z",
                        "next_steps": "w",
                    },
                ],
            }
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"] == {"imported": 2, "skipped": 1}


@pytest.mark.asyncio
async def test_invoke_import_records_invalid_payload(api_client):
    """Malformed batch input returns a typed VALIDATION_ERROR, not a 500."""
    res = await api_client.post(
        "/api/tools/code_agent_flow_viz/operations/import_records",
        json={"payload": {"records": "not-a-list"}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_audit_endpoint_records_invoke(api_client):
    await api_client.post(
        "/api/tools/blank_tool/operations/echo", json={"payload": {"input": "audit me"}}
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
        "/api/tools/chat_tool/operations/create_session",
        json={"payload": {"title": "My Chat"}},
    )
    body = res.json()
    assert body["success"] is True
    session_id = body["data"]["session"]["id"]
    assert body["data"]["session"]["title"] == "My Chat"
    assert body["data"]["session"]["tool_id"] == "chat_tool"

    # list
    res = await api_client.post(
        "/api/tools/chat_tool/operations/list_sessions", json={"payload": {}}
    )
    sessions = res.json()["data"]["sessions"]
    assert sessions[0]["id"] == session_id

    # get one
    res = await api_client.post(
        "/api/tools/chat_tool/operations/get_session",
        json={"payload": {"session_id": session_id}},
    )
    assert res.json()["data"]["session"]["tool_id"] == "chat_tool"

    # messages start empty
    res = await api_client.post(
        "/api/tools/chat_tool/operations/list_messages",
        json={"payload": {"session_id": session_id}},
    )
    assert res.json()["data"]["messages"] == []

    # missing session -> NOT_FOUND
    res = await api_client.post(
        "/api/tools/chat_tool/operations/get_session",
        json={"payload": {"session_id": "does-not-exist"}},
    )
    assert res.json()["error"]["code"] == "NOT_FOUND"

    # delete -> gone
    res = await api_client.post(
        "/api/tools/chat_tool/operations/delete_session",
        json={"payload": {"session_id": session_id}},
    )
    assert res.json()["data"]["deleted"] is True
    res = await api_client.post(
        "/api/tools/chat_tool/operations/get_session",
        json={"payload": {"session_id": session_id}},
    )
    assert res.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_chat_messages_returned_chronological(api_client, db):
    """History reload shows the conversation oldest→newest, and a page limit
    returns the NEWEST messages (tail-first), not the oldest."""
    from app.tool_plugins.chat_tool.repository import add_message, create_session

    session = await create_session(db, title="order", tool_id="chat_tool")
    await db.commit()
    for text in ("first", "second", "third", "fourth", "fifth"):
        await add_message(db, session.id, "user", text)
    await db.commit()

    res = await api_client.post(
        "/api/tools/chat_tool/operations/list_messages",
        json={"payload": {"session_id": session.id}},
    )
    messages = res.json()["data"]["messages"]
    assert [m["content"] for m in messages] == [
        "first", "second", "third", "fourth", "fifth",
    ]

    # A page smaller than the conversation returns the tail, not the head.
    res = await api_client.post(
        "/api/tools/chat_tool/operations/list_messages",
        json={"payload": {"session_id": session.id, "limit": 2}},
    )
    assert [m["content"] for m in res.json()["data"]["messages"]] == [
        "fourth", "fifth",
    ]


@pytest.mark.asyncio
async def test_rate_limit_429(api_client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_per_minute", 3)
    monkeypatch.setattr(ratelimit, "_redis_ok", False)  # skip redis probe
    ratelimit._memory.clear()

    statuses = []
    for _ in range(4):
        res = await api_client.post(
            "/api/tools/blank_tool/operations/echo", json={"payload": {"input": "x"}}
        )
        statuses.append(res.status_code)

    assert statuses[:3] == [200, 200, 200]
    assert statuses[3] == 429
    assert res.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_rate_limit_global_429(api_client, monkeypatch):
    """The global budget caps spend across distinct clients/IPs."""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_per_minute", 100)
    monkeypatch.setattr(settings, "rate_limit_global_per_minute", 2)
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    monkeypatch.setattr(ratelimit, "_redis_ok", False)
    ratelimit._memory.clear()

    statuses = []
    for ip in ("1.1.1.1", "2.2.2.2", "3.3.3.3"):
        res = await api_client.post(
            "/api/tools/blank_tool/operations/echo",
            json={"payload": {"input": "x"}},
            headers={"x-forwarded-for": ip},
        )
        statuses.append(res.status_code)

    assert statuses[:2] == [200, 200]
    assert statuses[2] == 429


@pytest.mark.asyncio
async def test_audit_log_redacts_secrets(api_client):
    """Live credentials in an invoke payload must never reach the audit log."""
    await api_client.post(
        "/api/tools/blank_tool/operations/echo",
        json={
            "payload": {
                "input": "hi",
                "session_api_key": "sk-very-secret-key",
                "api_key": "another-secret",
            }
        },
    )
    res = await api_client.get("/api/audit/tool-calls?tool_id=blank_tool&limit=1")
    body = res.json()
    assert body["success"] is True
    record = body["data"]["records"][0]
    assert "sk-very-secret-key" not in record["input_data"]
    assert "another-secret" not in record["input_data"]
    assert "[REDACTED]" in record["input_data"]


@pytest.mark.asyncio
async def test_invoke_prunes_audit_under_small_cap(api_client, monkeypatch):
    """The invoke path keeps the audit table under AUDIT_MAX_RECORDS."""
    monkeypatch.setattr(settings, "audit_max_records", 3)
    for i in range(5):
        res = await api_client.post(
            "/api/tools/blank_tool/operations/echo",
            json={"payload": {"input": f"call {i}"}},
        )
        assert res.status_code == 200

    res = await api_client.get("/api/audit/tool-calls")
    assert res.json()["success"] is True
    assert res.json()["data"]["total"] == 3


@pytest.mark.asyncio
async def test_invoke_coerces_non_string_input(api_client):
    res = await api_client.post(
        "/api/tools/blank_tool/operations/echo", json={"payload": {"input": 123}}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["echo"] == "123"


@pytest.mark.asyncio
async def test_request_body_size_capped(api_client):
    huge = {"payload": {"input": "x" * 2_000_000}}
    res = await api_client.post(
        "/api/tools/blank_tool/operations/echo",
        content=__import__("json").dumps(huge),
        headers={"content-type": "application/json"},
    )
    assert res.status_code == 413


@pytest.mark.asyncio
async def test_request_body_chunked_rejected(api_client):
    """A chunked body has no Content-Length, so the header cap alone would be
    bypassed — the middleware must reject Transfer-Encoding outright."""
    res = await api_client.post(
        "/api/tools/blank_tool/operations/echo",
        content=b'{"payload":{"input":"x"}}',
        headers={"transfer-encoding": "chunked", "content-type": "application/json"},
    )
    assert res.status_code == 413


@pytest.mark.asyncio
async def test_client_ip_respects_proxy_trust_setting(monkeypatch):
    fake = SimpleNamespace(
        headers={"x-forwarded-for": "9.9.9.9"}, client=SimpleNamespace(host="1.1.1.1")
    )
    monkeypatch.setattr(settings, "trust_proxy_headers", False)
    assert client_ip(fake) == "1.1.1.1"  # spoofed XFF ignored

    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    assert client_ip(fake) == "9.9.9.9"  # trusted proxy path used
