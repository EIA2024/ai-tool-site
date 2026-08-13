import { post } from "./api";
import { RealtimeClient } from "./realtime";
import type { ToolClient } from "../types";

/** REST path for one request-response operation. */
export function operationPath(toolId: string, operation: string): string {
  return `/tools/${toolId}/operations/${operation}`;
}

/**
 * Bind a ToolClient to one tool id. Custom plugins receive this and call
 * `invoke(operation, payload)` / `connect(operation)` — they never build URLs
 * or touch the transport directly.
 */
export function createToolClient(toolId: string): ToolClient {
  return {
    toolId,
    invoke(operation, payload = {}, opts) {
      return post(operationPath(toolId, operation), { payload }, opts);
    },
    connect(operation) {
      return new RealtimeClient(toolId, operation);
    },
  };
}
