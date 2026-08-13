import { describe, expect, it } from "vitest";
import {
  hasPluginUi,
  pluginLoaderFor,
  pluginModuleKeys,
} from "../src/tool_plugins/registry";

describe("tool_plugins registry", () => {
  it("inventories the three custom tools and no schema tool", () => {
    expect(pluginModuleKeys).toContain("./chat_tool/index.tsx");
    expect(pluginModuleKeys).toContain("./code_agent_flow_viz/index.tsx");
    expect(pluginModuleKeys).toContain("./task_decomposer/index.tsx");
    expect(pluginModuleKeys).not.toContain("./blank_tool/index.tsx");
  });

  it("resolves loaders only for tools with a custom UI entry", () => {
    expect(pluginLoaderFor("chat_tool")).toBeTypeOf("function");
    expect(pluginLoaderFor("code_agent_flow_viz")).toBeTypeOf("function");
    expect(pluginLoaderFor("task_decomposer")).toBeTypeOf("function");
    // Schema tools have no custom UI, and unknown tools have none either.
    expect(pluginLoaderFor("blank_tool")).toBeUndefined();
    expect(pluginLoaderFor("does_not_exist")).toBeUndefined();
    expect(hasPluginUi("chat_tool")).toBe(true);
    expect(hasPluginUi("blank_tool")).toBe(false);
  });
});
