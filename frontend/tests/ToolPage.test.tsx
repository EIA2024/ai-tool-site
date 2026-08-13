import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import ToolPage from "../src/pages/ToolPage";
import type { ToolManifest } from "../src/types";

function renderToolPage(toolId: string) {
  return render(
    <MemoryRouter initialEntries={[`/tools/${toolId}`]}>
      <Routes>
        <Route path="/tools/:toolId" element={<ToolPage />} />
      </Routes>
    </MemoryRouter>
  );
}

function stubToolResponse(tool: ToolManifest | null, error?: { code: string; message: string }) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () =>
        tool
          ? { success: true, data: { tool } }
          : { success: false, error },
    })
  );
}

const BLANK_MANIFEST: ToolManifest = {
  contract_version: "1",
  id: "blank_tool",
  version: "1.0.0",
  name: "Blank Tool",
  description: "A schema-rendered request-response plugin template",
  ui: { kind: "schema", layout: "standard" },
  operations: [
    {
      id: "echo",
      transport: "request-response",
      input_schema: {
        type: "object",
        properties: { input: { type: "string", title: "Input", default: "" } },
      },
      output_schema: {},
    },
  ],
};

const CUSTOM_MISSING: ToolManifest = {
  contract_version: "1",
  id: "custom_missing",
  version: "1.0.0",
  name: "Custom Missing",
  description: "A custom tool with no frontend UI",
  ui: { kind: "custom", layout: "standard" },
  operations: [
    { id: "op", transport: "request-response", input_schema: {}, output_schema: {} },
  ],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ToolPage dispatch", () => {
  it("renders the schema form for a schema-kind tool", async () => {
    stubToolResponse(BLANK_MANIFEST);
    renderToolPage("blank_tool");

    await waitFor(() => expect(screen.getByText("Blank Tool")).toBeInTheDocument());
    // The generic schema renderer generated a form from input_schema.
    expect(screen.getByLabelText(/Input/)).toBeInTheDocument();
  });

  it("shows a compatibility error when a custom tool has no UI entry", async () => {
    stubToolResponse(CUSTOM_MISSING);
    renderToolPage("custom_missing");

    await waitFor(() => expect(screen.getByText(/没有找到对应的插件/)).toBeInTheDocument());
  });

  it("shows an error for an unknown tool", async () => {
    stubToolResponse(null, { code: "NOT_FOUND", message: "Tool 'nope' not found" });
    renderToolPage("nope");

    await waitFor(() =>
      expect(screen.getByText("Tool 'nope' not found")).toBeInTheDocument()
    );
  });
});
