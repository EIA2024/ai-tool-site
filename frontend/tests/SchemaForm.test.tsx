import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SchemaForm } from "../src/pages/schema/SchemaTool";
import type { JsonSchema } from "../src/types";

const SCHEMA: JsonSchema = {
  type: "object",
  properties: {
    input: { type: "string", title: "Input", default: "" },
    count: { type: "integer", title: "Count" },
    done: { type: "boolean", title: "Done" },
  },
  required: ["input"],
};

describe("SchemaForm", () => {
  it("renders a field per property and coerces values on submit", () => {
    const onSubmit = vi.fn();
    render(<SchemaForm schema={SCHEMA} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText(/Input/), { target: { value: "hi" } });
    fireEvent.change(screen.getByLabelText(/Count/), { target: { value: "42" } });
    fireEvent.click(screen.getByText("Run"));

    expect(onSubmit).toHaveBeenCalledWith({ input: "hi", count: 42, done: false });
  });

  it("coerces array input from JSON or newline-separated text", () => {
    const listSchema: JsonSchema = {
      type: "object",
      properties: {
        tags: { type: "array", title: "Tags", items: { type: "string" } },
      },
    };
    const onSubmit = vi.fn();
    const { unmount } = render(<SchemaForm schema={listSchema} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText(/Tags/), { target: { value: "a\nb\nc" } });
    fireEvent.click(screen.getByText("Run"));
    expect(onSubmit).toHaveBeenCalledWith({ tags: ["a", "b", "c"] });

    unmount();
    const onSubmit2 = vi.fn();
    render(<SchemaForm schema={listSchema} onSubmit={onSubmit2} />);
    fireEvent.change(screen.getByLabelText(/Tags/), {
      target: { value: '["x","y"]' },
    });
    fireEvent.click(screen.getByText("Run"));
    expect(onSubmit2).toHaveBeenCalledWith({ tags: ["x", "y"] });
  });
});
