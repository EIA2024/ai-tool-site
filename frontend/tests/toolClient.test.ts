import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../src/lib/api";
import { realtimeUrl, RealtimeClient } from "../src/lib/realtime";
import { createToolClient, operationPath } from "../src/lib/toolClient";
import type { RealtimeServerEvent } from "../src/types";

beforeEach(() => {
  vi.stubEnv("VITE_API_BASE", "");
});

afterEach(() => {
  vi.unstubAllEnvs();
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

  it("passes caller cancellation to fetch and returns ABORTED", async () => {
    const controller = new AbortController();
    let fetchSignal: AbortSignal | null | undefined;
    const fetchMock = vi.fn().mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          fetchSignal = init.signal;
          init.signal?.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        })
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = createToolClient("blank_tool");
    const request = client.invoke("echo", {}, {
      timeoutMs: 10_000,
      signal: controller.signal,
    });
    controller.abort();

    expect(fetchSignal?.aborted).toBe(true);
    await expect(request).rejects.toMatchObject<ApiError>({
      code: "ABORTED",
      status: 0,
    });
  });
});

describe("realtimeUrl", () => {
  it("uses the page origin for the same-origin API default", () => {
    const url = realtimeUrl("chat_tool", "send_message");
    expect(url).toBe(
      "ws://localhost:3000/ws/tools/chat_tool/operations/send_message"
    );
  });

  it.each([
    ["http://api.example.com/api", "ws://api.example.com"],
    ["https://api.example.com/api", "wss://api.example.com"],
  ])("derives the WebSocket origin from %s", (apiBase, wsOrigin) => {
    vi.stubEnv("VITE_API_BASE", apiBase);

    expect(realtimeUrl("chat_tool", "send_message")).toBe(
      `${wsOrigin}/ws/tools/chat_tool/operations/send_message`
    );
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

  it("ignores callbacks from a socket replaced by reopen", () => {
    vi.stubGlobal("WebSocket", FakeWebSocket);
    const events: RealtimeServerEvent[] = [];
    const statuses: string[] = [];
    const client = new RealtimeClient("chat_tool", "send_message");
    client.onEvent((event) => events.push(event));
    client.onStatus((status) => statuses.push(status));

    client.open();
    const oldSocket = FakeWebSocket.instances[0];
    const oldHandlers = {
      open: oldSocket.onopen,
      close: oldSocket.onclose,
      error: oldSocket.onerror,
      message: oldSocket.onmessage,
    };
    client.open();

    expect(oldSocket.onopen).toBeNull();
    expect(oldSocket.onclose).toBeNull();
    expect(oldSocket.onerror).toBeNull();
    expect(oldSocket.onmessage).toBeNull();

    oldHandlers.open?.();
    oldHandlers.error?.();
    oldHandlers.message?.({
      data: JSON.stringify({ type: "ready", tool_id: "old" }),
    });
    oldHandlers.close?.();

    expect(statuses).toEqual([]);
    expect(events).toEqual([]);
  });

  it("ignores callbacks after close", () => {
    vi.stubGlobal("WebSocket", FakeWebSocket);
    const statuses: string[] = [];
    const client = new RealtimeClient("chat_tool", "send_message");
    client.onStatus((status) => statuses.push(status));
    client.open();
    const ws = FakeWebSocket.instances[0];
    const onopen = ws.onopen;

    client.close();
    onopen?.();

    expect(ws.onopen).toBeNull();
    expect(ws.onerror).toBeNull();
    expect(ws.onmessage).toBeNull();
    expect(ws.onclose).toBeNull();
    expect(statuses).toEqual([]);
  });
});
