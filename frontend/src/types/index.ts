export interface ToolMeta {
  tool_id: string;
  name: string;
  description: string;
  mode: "request-response" | "realtime";
}

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
}

export interface WsMessage {
  type: string;
  content: string;
  sender: string;
  timestamp: string;
}

/* ── Code Agent Flow Visualizer types ── */

export interface StageDefinition {
  key: string;
  number: number;
  title: string;
  goals: string[];
  promptTemplate: string;
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
