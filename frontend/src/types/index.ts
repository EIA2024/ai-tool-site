/* ── Host–plugin contract (mirrors the backend ToolManifest) ── */

export type Transport = "request-response" | "realtime";
export type UiKind = "schema" | "custom";
export type UiLayout = "standard" | "fullscreen";

/** A loose JSON Schema, sufficient for the generic schema renderer. */
export interface JsonSchema {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  items?: JsonSchema;
  enum?: unknown[];
  anyOf?: JsonSchema[];
  minLength?: number;
  maxLength?: number;
  minimum?: number;
  maximum?: number;
  [key: string]: unknown;
}

export interface OperationManifest {
  id: string;
  transport: Transport;
  input_schema: JsonSchema;
  output_schema: JsonSchema;
}

export interface ToolUi {
  kind: UiKind;
  layout: UiLayout;
}

export interface ToolManifest {
  contract_version: string;
  id: string;
  version: string;
  name: string;
  description: string;
  ui: ToolUi;
  operations: OperationManifest[];
}

/* ── API envelope ── */

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
}

/* ── Public runtime config (GET /api/config) ── */

export interface PublicConfig {
  models: string[];
  default_model: string;
}

/* ── Audit / usage ── */

export interface AuditRecord {
  id: string;
  tool_id: string;
  success: boolean;
  input_data: string | null;
  output_data: string | null;
  created_at: string | null;
}

export interface ToolUsageSummary {
  tool_id: string;
  calls: number;
  failures: number;
}

export interface AuditSummaryData {
  total: number;
  by_tool: ToolUsageSummary[];
}

export interface AuditListData {
  records: AuditRecord[];
  total: number;
  limit: number;
  offset: number;
}

/* ── Realtime protocol ── */

export type RealtimeStatus = "connecting" | "connected" | "disconnected" | "error";

export type RealtimeServerEvent =
  | { type: "ready"; tool_id?: string; operation_id?: string }
  | { type: "progress"; request_id: string; data: Record<string, unknown> }
  | { type: "delta"; request_id: string; data: Record<string, unknown> }
  | { type: "result"; request_id: string; data: Record<string, unknown> }
  | {
      type: "error";
      request_id: string | null;
      data: { code: string; message: string };
    };

/** The bound realtime connection returned by `ToolClient.connect`. */
export interface RealtimeConnection {
  readonly url: string;
  readonly isOpen: boolean;
  open(): void;
  send(payload: Record<string, unknown>): string;
  close(): void;
  onEvent(handler: (event: RealtimeServerEvent) => void): void;
  onStatus(handler: (status: RealtimeStatus) => void): void;
}

/* ── ToolClient ── */

export interface ToolClient {
  readonly toolId: string;
  invoke<T = unknown>(
    operation: string,
    payload?: Record<string, unknown>,
    opts?: { timeoutMs?: number }
  ): Promise<ApiResponse<T>>;
  connect(operation: string): RealtimeConnection;
}

/** Props every custom plugin's default export receives. */
export interface ToolPluginProps {
  client: ToolClient;
  manifest: ToolManifest;
}
