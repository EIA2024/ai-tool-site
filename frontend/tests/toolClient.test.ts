import { afterEach, describe, expect, it, vi } from "vitest";
import { realtimeUrl, RealtimeClient } from "../src/lib/realtime";
import { createToolClient, operationPath } from "../src/lib/toolClient";
import type { RealtimeServerEvent } from "../src/types";

afterEach(() => {
  vi.unstubAllGlobals();
  FakeWebSocket.instances = [];
});

describe("operationPath", () => {
  it("builds the unified REST operation path", () => {
    expect(operationPath("blank_tool", "echo")).toBe(
      "/tools/blank_tool/operations/echo"
    );
    expect(operationPath("chat_tool", "list_sessions")).toBe(
      "/tools/chat_tool/operations/list_sessions"
    );
  });
});

describe("ToolClient.invoke", () => {
  it("POSTs a { payload } envelope to the operation path", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true, data: { echo: "hi" } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const client = createToolClient("blank_tool");
    const res = await client.invoke<{ echo: string }>("echo", { input: "hi" });

    expect(res.success).toBe(true);
    expect(res.data?.echo).toBe("hi");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/tools/blank_tool/operations/echo",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ payload: { input: "hi" } }),
      })
    );
  });
});

describe("realtimeUrl", () => {
  it("routes to the unified WebSocket operation path", () => {
    const url = realtimeUrl("chat_tool", "send_message");
    expect(url.startsWith("ws://")).toBe(true);
    expect(url).toContain("/ws/tools/chat_tool/operations/send_message");
  });
});

class FakeWebSocket {
  static OPEN = 1;
  static instances: FakeWebSocket[] = [];

  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;

  constructor(public readonly url: string) {
    FakeWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = 3;
    this.onclose?.();
  }
}

describe("RealtimeClient", () => {
  it("connects to the operation URL and parses server frames", () => {
    vi.stubGlobal("WebSocket", FakeWebSocket);
    const events: RealtimeServerEvent[] = [];
    const statuses: string[] = [];

    const client = new RealtimeClient("chat_tool", "send_message");
    client.onEvent((event) => events.push(event));
    client.onStatus((status) => statuses.push(status));
    client.open();

    const ws = FakeWebSocket.instances[0];
    expect(ws.url).toContain("/ws/tools/chat_tool/operations/send_message");

    ws.onopen?.();
    expect(statuses).toContain("connected");

    ws.onmessage?.({ data: JSON.stringify({ type: "ready", tool_id: "chat_tool" }) });
    ws.onmessage?.({
      data: JSON.stringify({
        type: "delta",
        request_id: "r1",
        data: { content: "你好" },
      }),
    });
    expect(events.map((event) => event.type)).toEqual(["ready", "delta"]);
  });

  it("sends invoke frames with a request_id", () => {
    vi.stubGlobal("WebSocket", FakeWebSocket);
    const client = new RealtimeClient("chat_tool", "send_message");
    client.open();
    const ws = FakeWebSocket.instances[0];
    ws.readyState = FakeWebSocket.OPEN;

    const requestId = client.send({ content: "hello", session_id: "abc" });

    expect(ws.sent).toHaveLength(1);
    const frame = JSON.parse(ws.sent[0]);
    expect(frame.type).toBe("invoke");
    expect(frame.request_id).toBe(requestId);
    expect(frame.payload).toEqual({ content: "hello", session_id: "abc" });
  });

  it("ignores malformed frames", () => {
    vi.stubGlobal("WebSocket", FakeWebSocket);
    const events: RealtimeServerEvent[] = [];
    const client = new RealtimeClient("chat_tool", "send_message");
    client.onEvent((event) => events.push(event));
    client.open();
    const ws = FakeWebSocket.instances[0];

    expect(() => ws.onmessage?.({ data: "not json" })).not.toThrow();
    expect(events).toHaveLength(0);
  });
});
