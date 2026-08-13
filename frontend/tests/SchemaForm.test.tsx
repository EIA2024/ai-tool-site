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

  it("submits integer exponent notation without truncating it", () => {
    const onSubmit = vi.fn();
    render(<SchemaForm schema={SCHEMA} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText(/Input/), { target: { value: "hi" } });
    fireEvent.change(screen.getByLabelText(/Count/), { target: { value: "1e2" } });
    fireEvent.click(screen.getByText("Run"));

    expect(onSubmit).toHaveBeenCalledWith({ input: "hi", count: 100, done: false });
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

  it("blocks submission when a required field is empty", () => {
    const constrainedSchema: JsonSchema = {
      type: "object",
      properties: {
        name: {
          type: "string",
          title: "Name",
          minLength: 2,
          maxLength: 10,
        },
        count: {
          type: "integer",
          title: "Count",
          minimum: 1,
          maximum: 5,
        },
        ratio: {
          type: "number",
          title: "Ratio",
          minimum: 0,
          maximum: 1,
        },
      },
      required: ["name", "count"],
    };
    const onSubmit = vi.fn();

    render(<SchemaForm schema={constrainedSchema} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText(/Count/), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it.each(["a", "name that is too long"])(
    "blocks submission when a string violates its length constraints: %s",
    (name) => {
      const schema: JsonSchema = {
        type: "object",
        properties: {
          name: {
            type: "string",
            title: "Name",
            minLength: 2,
            maxLength: 10,
          },
        },
        required: ["name"],
      };
      const onSubmit = vi.fn();
      render(<SchemaForm schema={schema} onSubmit={onSubmit} />);

      fireEvent.change(screen.getByLabelText(/Name/), { target: { value: name } });
      fireEvent.click(screen.getByRole("button", { name: "Run" }));

      expect(onSubmit).not.toHaveBeenCalled();
    }
  );

  it.each(["0", "6"])(
    "blocks submission when a number is outside its allowed range: %s",
    (count) => {
      const schema: JsonSchema = {
        type: "object",
        properties: {
          count: {
            type: "integer",
            title: "Count",
            minimum: 1,
            maximum: 5,
          },
        },
        required: ["count"],
      };
      const onSubmit = vi.fn();
      render(<SchemaForm schema={schema} onSubmit={onSubmit} />);

      fireEvent.change(screen.getByLabelText(/Count/), { target: { value: count } });
      fireEvent.click(screen.getByRole("button", { name: "Run" }));

      expect(onSubmit).not.toHaveBeenCalled();
    }
  );

  it("submits values that satisfy all constraints", () => {
    const schema: JsonSchema = {
      type: "object",
      properties: {
        name: { type: "string", title: "Name", minLength: 2, maxLength: 10 },
        count: { type: "integer", title: "Count", minimum: 1, maximum: 5 },
      },
      required: ["name", "count"],
    };
    const onSubmit = vi.fn();
    render(<SchemaForm schema={schema} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText(/Name/), { target: { value: "valid" } });
    fireEvent.change(screen.getByLabelText(/Count/), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    expect(onSubmit).toHaveBeenCalledWith({ name: "valid", count: 3 });
  });

  it("omits an empty optional number instead of submitting NaN", () => {
    const onSubmit = vi.fn();
    render(<SchemaForm schema={SCHEMA} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText(/Input/), { target: { value: "hi" } });
    fireEvent.click(screen.getByText("Run"));

    expect(onSubmit).toHaveBeenCalledWith({ input: "hi", done: false });
  });
});
