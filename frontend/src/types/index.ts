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
