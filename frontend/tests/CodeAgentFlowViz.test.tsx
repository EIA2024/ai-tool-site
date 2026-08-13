import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import CodeAgentFlowVizPlugin from "../src/tool_plugins/code_agent_flow_viz";
import type {
  ApiResponse,
  ToolClient,
  ToolManifest,
} from "../src/types";
import type {
  ListRecordsData,
  PracticeRecord,
} from "../src/tool_plugins/code_agent_flow_viz/types";

const MANIFEST: ToolManifest = {
  contract_version: "1",
  id: "code_agent_flow_viz",
  version: "1.0.0",
  name: "Code Agent Flow Visualizer",
  description: "Practice records",
  ui: { kind: "custom", layout: "standard" },
  operations: [],
};

function record(id: string): PracticeRecord {
  return {
    id,
    stage_key: "goal_setting",
    user_input: `input ${id}`,
    agent_output: "",
    feedback: "",
    next_steps: "",
    content_hash: `hash-${id}`,
    created_at: null,
    updated_at: null,
  };
}

function renderPlugin(invoke: ReturnType<typeof vi.fn>) {
  const client = {
    toolId: "code_agent_flow_viz",
    invoke,
  } as unknown as ToolClient;

  return render(
    <MemoryRouter>
      <CodeAgentFlowVizPlugin client={client} manifest={MANIFEST} />
    </MemoryRouter>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CodeAgentFlowVizPlugin", () => {
  it.each([
    {
      name: "returns success false",
      failedPage: {
        success: false,
        error: { code: "EXPORT_FAILED", message: "Page unavailable" },
      } satisfies ApiResponse<ListRecordsData>,
      expectedError: "Page unavailable",
    },
    {
      name: "throws",
      failedPage: new Error("Network failed"),
      expectedError: "Network failed",
    },
  ])("does not download partial JSON when a later page $name", async ({
    failedPage,
    expectedError,
  }) => {
    const firstPage = Array.from({ length: 1000 }, (_, index) =>
      record(String(index))
    );
    const invoke = vi
      .fn()
      .mockResolvedValueOnce({
        success: true,
        data: { records: [firstPage[0]], total: 1001 },
      })
      .mockResolvedValueOnce({
        success: true,
        data: { records: firstPage, total: 1001 },
      });
    if (failedPage instanceof Error) {
      invoke.mockRejectedValueOnce(failedPage);
    } else {
      invoke.mockResolvedValueOnce(failedPage);
    }
    const createObjectURL = vi.fn();
    vi.stubGlobal("URL", {
      createObjectURL,
      revokeObjectURL: vi.fn(),
    });

    renderPlugin(invoke);
    await screen.findByText("History (1001)");
    fireEvent.click(screen.getAllByRole("button", { name: "Export JSON" })[0]);

    await waitFor(() =>
      expect(screen.getByText(new RegExp(expectedError))).toBeInTheDocument()
    );
    expect(createObjectURL).not.toHaveBeenCalled();
  });

  it("decrements the total after deleting a record", async () => {
    const records = [record("one"), record("two")];
    const invoke = vi
      .fn()
      .mockResolvedValueOnce({
        success: true,
        data: { records, total: 5 },
      })
      .mockResolvedValueOnce({ success: true });

    renderPlugin(invoke);
    await screen.findByText("History (5)");
    fireEvent.click(screen.getAllByRole("button", { name: "Delete" })[0]);

    await waitFor(() => expect(screen.getByText("History (4)")).toBeInTheDocument());
    expect(screen.queryByText("input one")).not.toBeInTheDocument();
  });

  it("does not decrement the total below zero", async () => {
    const records = [record("one"), record("two")];
    const invoke = vi
      .fn()
      .mockResolvedValueOnce({
        success: true,
        data: { records, total: 1 },
      })
      .mockResolvedValue({ success: true });

    renderPlugin(invoke);
    await screen.findByText("History (1)");
    fireEvent.click(screen.getAllByRole("button", { name: "Delete" })[0]);
    await waitFor(() =>
      expect(screen.queryByText("input one")).not.toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(screen.getByText("History (0)")).toBeInTheDocument());
  });
});
