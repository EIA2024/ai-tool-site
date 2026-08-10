export interface ToolMeta {
  tool_id: string;
  name: string;
  description: string;
  mode: "request-response" | "realtime";
  config?: Record<string, unknown>;
}

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
}

export interface WsMessage {
  type: string;
  /** Present on "message" frames — the bubble body. */
  content?: string;
  /** Present on "message" frames — the speaker ("user" | "assistant"). */
  sender?: string;
  timestamp?: string;
  /** Present on the server's "connected" frame — carries the DB session id. */
  session_id?: string;
  /** Present on the server's "connected" frame — selectable model ids. */
  models?: string[];
  /** Present on the server's "connected" frame — the default model. */
  default_model?: string;
  /** Present on the server's "error" frames — human-readable reason. */
  message?: string;
}

/* ── Public runtime config (GET /api/config) ── */

export interface PublicConfig {
  deepseek_models: string[];
  deepseek_default_model: string;
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

/* ── Chat sessions & messages ── */

export interface ChatSession {
  id: string;
  title: string;
  tool_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string | null;
}

export interface ChatSessionListData {
  sessions: ChatSession[];
}

export interface ChatMessagesData {
  messages: ChatMessage[];
}

/* ── Code Agent Flow Visualizer types ── */

export interface StageDefinition {
  key: string;
  number: number;
  title: string;
  hint: string;
  goals: string[];
  promptTemplate: string;
  promptTemplateZh: string;
  variables: string[];
  checklist: string[];
  commonErrors: string[];
  completionCriteria: string[];
}

export interface PracticeRecord {
  id: string;
  stage_key: string;
  user_input: string;
  agent_output: string;
  feedback: string;
  next_steps: string;
  content_hash: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface InvokePayload {
  action: "save_record" | "list_records" | "get_record" | "delete_record";
  [key: string]: unknown;
}

export interface SaveRecordPayload extends InvokePayload {
  action: "save_record";
  stage_key: string;
  user_input: string;
  agent_output: string;
  feedback: string;
  next_steps: string;
}

export interface SaveRecordData {
  record: PracticeRecord;
  created: boolean;
}

export interface ListRecordsData {
  records: PracticeRecord[];
}

/* ── Task Decomposer types ── */

export interface TaskAnalysis {
  goal: string;
  context: string[];
  constraints: string[];
  done_when: string[];
  failure_cases: string[];
  verification: string[];
  missing_questions: string[];
  risk_level: "low" | "medium" | "high";
  non_goals: string[];
  agent_prompt: string;
}

export interface TaskDecomposerInput {
  raw_task: string;
  context: string;
  task_type: string;
  model: string;
  risk_hints: string[];
  session_api_key?: string;
}

export interface HistoryRecord {
  id: string;
  raw_task: string;
  context: string;
  task_type: string;
  model_name: string;
  risk_hints: string[];
  risk_level: string;
  structured_output: TaskAnalysis;
  created_at: string | null;
}

export interface AnalyzeTaskData {
  analysis: TaskAnalysis;
  model: string;
}

export interface ListHistoryData {
  records: HistoryRecord[];
}
