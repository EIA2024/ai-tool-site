import type { ComponentType } from "react";
import type { ToolPluginProps } from "../types";

/**
 * Lazy-load map of custom-tool UIs, keyed by tool id. A tool whose id has a
 * matching `src/tool_plugins/<id>/index.tsx` is a "custom" UI plugin; tools
 * without one are rendered by the generic schema renderer (or reported as a
 * missing-UI compatibility error).
 */
type PluginModule = { default: ComponentType<ToolPluginProps> };

const modules = import.meta.glob<PluginModule>("./*/index.tsx");

export function pluginLoaderFor(
  toolId: string
): (() => Promise<PluginModule>) | undefined {
  return modules[`./${toolId}/index.tsx`];
}

export function hasPluginUi(toolId: string): boolean {
  return Boolean(modules[`./${toolId}/index.tsx`]);
}

/** The raw glob keys, exposed for tests to assert the plugin inventory. */
export const pluginModuleKeys: string[] = Object.keys(modules);
