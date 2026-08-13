import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import UsagePage from "../src/pages/UsagePage";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("UsagePage", () => {
  it("renders public audit metadata without an input details column", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (url: string) => ({
        ok: true,
        status: 200,
        json: async () =>
          url.endsWith("/audit/summary")
            ? {
                success: true,
                data: {
                  total: 1,
                  by_tool: [{ tool_id: "blank_tool", calls: 1, failures: 0 }],
                },
              }
            : {
                success: true,
                data: {
                  records: [
                    {
                      id: "record-1",
                      tool_id: "blank_tool",
                      success: true,
                      input_data: "sensitive input",
                      output_data: "sensitive output",
                      created_at: "2026-08-13T12:00:00",
                    },
                  ],
                  total: 1,
                  limit: 20,
                  offset: 0,
                },
              },
      }))
    );

    render(<UsagePage />);

    await waitFor(() => expect(screen.getAllByText("blank_tool")).toHaveLength(2));
    expect(screen.getByText("ok")).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Input" })).not.toBeInTheDocument();
    expect(screen.queryByText("sensitive input")).not.toBeInTheDocument();
    expect(screen.queryByText("sensitive output")).not.toBeInTheDocument();
  });
});
