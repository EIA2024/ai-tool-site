import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ChatToolPlugin from "../src/tool_plugins/chat_tool";
import MessageContent from "../src/tool_plugins/chat_tool/MessageContent";
import type { ChatMessagesData } from "../src/tool_plugins/chat_tool/types";
import type {
  ApiResponse,
  RealtimeConnection,
  RealtimeServerEvent,
  RealtimeStatus,
  ToolClient,
  ToolManifest,
} from "../src/types";

const manifest: ToolManifest = {
  contract_version: "1",
  id: "chat_tool",
  version: "1.0.0",
  name: "Chat Tool",
  description: "Chat",
  ui: { kind: "custom", layout: "standard" },
  operations: [],
};

const sessions = [
  { id: "a", title: "Session A", tool_id: null, created_at: null, updated_at: null },
  { id: "b", title: "Session B", tool_id: null, created_at: null, updated_at: null },
];

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

class FakeConnection implements RealtimeConnection {
  readonly url = "ws://test";
  isOpen = false;
  sent: Array<{ requestId: string; payload: Record<string, unknown> }> = [];
  private eventHandler: ((event: RealtimeServerEvent) => void) | null = null;
  private statusHandler: ((status: RealtimeStatus) => void) | null = null;

  open() {
    this.isOpen = true;
    this.statusHandler?.("connected");
  }

  send(payload: Record<string, unknown>) {
    const requestId = `request-${this.sent.length + 1}`;
    this.sent.push({ requestId, payload });
    return requestId;
  }

  close() {
    this.isOpen = false;
  }

  onEvent(handler: (event: RealtimeServerEvent) => void) {
    this.eventHandler = handler;
  }

  onStatus(handler: (status: RealtimeStatus) => void) {
    this.statusHandler = handler;
  }

  emit(event: RealtimeServerEvent) {
    this.eventHandler?.(event);
  }
}

function makeClient(
  invoke: ToolClient["invoke"],
  connection = new FakeConnection()
): { client: ToolClient; connection: FakeConnection } {
  return {
    client: { toolId: "chat_tool", invoke, connect: () => connection },
    connection,
  };
}

function success<T>(data: T): ApiResponse<T> {
  return { success: true, data };
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => success({ models: [], default_model: "" }),
    })
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("MessageContent untrusted content", () => {
  it("renders HTML and scripts as text instead of DOM", () => {
    const content = '<img src="x" onerror="alert(1)"><script>alert(1)</script>';
    const { container } = render(<MessageContent content={content} />);

    expect(container).toHaveTextContent(content);
    expect(container.querySelector("img")).not.toBeInTheDocument();
    expect(container.querySelector("script")).not.toBeInTheDocument();
  });

  it("drops dangerous link protocols and preserves HTTP links", () => {
    render(
      <MessageContent
        content={[
          "[script](javascript:alert)",
          "[data](data:text/html,unsafe)",
          "[safe](http://example.com/path)",
        ].join(" ")}
      />
    );

    expect(screen.queryByRole("link", { name: "script" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "data" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "safe" })).toHaveAttribute(
      "href",
      "http://example.com/path"
    );
  });
});

describe("ChatToolPlugin request ownership", () => {
  it("drops stale history after New Chat", async () => {
    const history = deferred<ApiResponse<ChatMessagesData>>();
    const { client } = makeClient(
      vi.fn((operation) => {
        if (operation === "list_sessions") return Promise.resolve(success({ sessions }));
        if (operation === "list_messages") return history.promise;
        return Promise.resolve(success({}));
      }) as ToolClient["invoke"]
    );

    render(<ChatToolPlugin client={client} manifest={manifest} />);
    fireEvent.click(await screen.findByRole("button", { name: "Session A" }));
    fireEvent.click(screen.getByRole("button", { name: "New Chat" }));

    await act(async () => {
      history.resolve(
        success({
          messages: [
            {
              id: "old",
              session_id: "a",
              role: "assistant",
              content: "stale history",
              created_at: null,
            },
          ],
        })
      );
    });

    expect(screen.queryByText("stale history")).not.toBeInTheDocument();
  });

  it("drops stale history after deleting the active session", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true));
    const history = deferred<ApiResponse<ChatMessagesData>>();
    const { client } = makeClient(
      vi.fn((operation) => {
        if (operation === "list_sessions") return Promise.resolve(success({ sessions }));
        if (operation === "list_messages") return history.promise;
        return Promise.resolve(success({}));
      }) as ToolClient["invoke"]
    );

    render(<ChatToolPlugin client={client} manifest={manifest} />);
    fireEvent.click(await screen.findByRole("button", { name: "Session A" }));
    fireEvent.click(screen.getAllByRole("button", { name: "Delete session" })[0]);
    await waitFor(() => expect(screen.queryByRole("button", { name: "Session A" })).not.toBeInTheDocument());

    await act(async () => {
      history.resolve(
        success({
          messages: [
            {
              id: "old",
              session_id: "a",
              role: "assistant",
              content: "deleted history",
              created_at: null,
            },
          ],
        })
      );
    });

    expect(screen.queryByText("deleted history")).not.toBeInTheDocument();
  });

  it("invalidates pending history when unmounted", async () => {
    const history = deferred<ApiResponse<ChatMessagesData>>();
    const { client, connection } = makeClient(
      vi.fn((operation) => {
        if (operation === "list_sessions") return Promise.resolve(success({ sessions }));
        if (operation === "list_messages") return history.promise;
        return Promise.resolve(success({}));
      }) as ToolClient["invoke"]
    );

    const view = render(<ChatToolPlugin client={client} manifest={manifest} />);
    fireEvent.click(await screen.findByRole("button", { name: "Session A" }));
    view.unmount();

    await act(async () => {
      history.resolve(success({ messages: [] }));
    });

    expect(connection.isOpen).toBe(false);
  });

  it("does not let session A stream events pollute session B or reactivate A", async () => {
    const { client, connection } = makeClient(
      vi.fn((operation) => {
        if (operation === "list_sessions") return Promise.resolve(success({ sessions }));
        if (operation === "list_messages") return Promise.resolve(success({ messages: [] }));
        return Promise.resolve(success({}));
      }) as ToolClient["invoke"]
    );

    render(<ChatToolPlugin client={client} manifest={manifest} />);
    fireEvent.click(await screen.findByRole("button", { name: "Session A" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Session A" })).toHaveClass("active")
    );
    fireEvent.change(screen.getByRole("textbox", { name: "Chat message" }), {
      target: { value: "ask A" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(connection.sent[0]).toEqual({
      requestId: "request-1",
      payload: { content: "ask A", session_id: "a" },
    });
    act(() => {
      connection.emit({
        type: "result",
        request_id: "another-request",
        data: {
          session_id: "a",
          message: { id: "wrong", session_id: "a", role: "assistant", content: "wrong request" },
        },
      });
    });
    expect(screen.queryByText("wrong request")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Session B" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Session B" })).toHaveClass("active")
    );
    act(() => {
      connection.emit({
        type: "progress",
        request_id: "request-1",
        data: { session_id: "a" },
      });
      connection.emit({
        type: "delta",
        request_id: "request-1",
        data: { content: "A partial" },
      });
      connection.emit({
        type: "result",
        request_id: "request-1",
        data: {
          session_id: "a",
          message: { id: "reply", session_id: "a", role: "assistant", content: "A result" },
        },
      });
    });

    expect(screen.queryByText("A partial")).not.toBeInTheDocument();
    expect(screen.queryByText("A result")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Session B" })).toHaveClass("active");
  });
});

describe("ChatToolPlugin load errors", () => {
  it("shows a retryable session-list error instead of an empty state", async () => {
    const invoke = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(success({ sessions }));
    const { client } = makeClient(invoke as ToolClient["invoke"]);

    render(<ChatToolPlugin client={client} manifest={manifest} />);
    expect(await screen.findByText("Failed to load sessions.")).toBeInTheDocument();
    expect(screen.queryByText("No sessions yet. Start a new chat.")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry sessions" }));
    expect(await screen.findByRole("button", { name: "Session A" })).toBeInTheDocument();
  });

  it("shows a retryable history error for unsuccessful responses", async () => {
    const invoke = vi.fn((operation) => {
      if (operation === "list_sessions") return Promise.resolve(success({ sessions }));
      if (operation === "list_messages") {
        return Promise.resolve({
          success: false,
          error: { code: "LOAD_FAILED", message: "history unavailable" },
        });
      }
      return Promise.resolve(success({}));
    });
    const { client } = makeClient(invoke as ToolClient["invoke"]);

    render(<ChatToolPlugin client={client} manifest={manifest} />);
    fireEvent.click(await screen.findByRole("button", { name: "Session A" }));

    expect(await screen.findByText("history unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry messages" })).toBeInTheDocument();
    expect(screen.queryByText("No messages yet — say hello!")).not.toBeInTheDocument();
  });
});
