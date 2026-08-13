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

export interface ChatSessionData {
  session: ChatSession;
}

export interface ChatMessagesData {
  messages: ChatMessage[];
}

export interface SendMessageData {
  session_id: string;
  message: ChatMessage;
}
