import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import ToolList from "../src/pages/ToolList";
import type { ToolManifest } from "../src/types";

const PUBLIC_TOOLS: ToolManifest[] = [
  {
    contract_version: "1",
    id: "chat_tool",
    version: "1.0.0",
    name: "Chat Tool",
    description: "Realtime multi-turn chat",
    ui: { kind: "custom", layout: "standard" },
    operations: [
      { id: "send_message", transport: "realtime", input_schema: {}, output_schema: {} },
      { id: "list_sessions", transport: "request-response", input_schema: {}, output_schema: {} },
    ],
  },
  {
    contract_version: "1",
    id: "code_agent_flow_viz",
    version: "1.0.0",
    name: "Code Agent Flow Visualizer",
    description: "Explore nine coding-agent workflow stages",
    ui: { kind: "custom", layout: "fullscreen" },
    operations: [
      { id: "list_records", transport: "request-response", input_schema: {}, output_schema: {} },
    ],
  },
  {
    contract_version: "1",
    id: "task_decomposer",
    version: "1.0.0",
    name: "Task Decomposer",
    description: "Turn vague requests into task cards",
    ui: { kind: "custom", layout: "fullscreen" },
    operations: [
      { id: "analyze_task", transport: "request-response", input_schema: {}, output_schema: {} },
    ],
  },
];

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ToolList (Dock)", () => {
  it("renders the tools the API returns and links to /tools/:id", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ success: true, data: { tools: PUBLIC_TOOLS } }),
      })
    );

    render(
      <MemoryRouter>
        <ToolList />
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText("Chat Tool")).toBeInTheDocument());

    // All three public tools are shown.
    expect(screen.getByText("Code Agent Flow Visualizer")).toBeInTheDocument();
    expect(screen.getByText("Task Decomposer")).toBeInTheDocument();

    // The Blank example is hidden (the backend omits it).
    expect(screen.queryByText("Blank Tool")).not.toBeInTheDocument();

    // Each card links to the single dynamic route.
    expect(screen.getByText("Chat Tool").closest("a")).toHaveAttribute(
      "href",
      "/tools/chat_tool"
    );
    expect(screen.getByText("Task Decomposer").closest("a")).toHaveAttribute(
      "href",
      "/tools/task_decomposer"
    );
  });
});
