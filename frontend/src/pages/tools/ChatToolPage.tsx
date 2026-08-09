import { useCallback, useEffect, useRef, useState } from "react";
import { del, get } from "../../lib/api";
import { WsClient } from "../../lib/ws";
import type {
  ChatMessagesData,
  ChatSession,
  ChatSessionListData,
  WsMessage,
} from "../../types";
import ChatMessage from "../../components/chat/ChatMessage";
import ChatInput from "../../components/chat/ChatInput";

interface UiMessage extends WsMessage {
  localId: string;
}

let localCounter = 0;

export default function ChatToolPage() {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [status, setStatus] = useState("disconnected");
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const clientRef = useRef<WsClient | null>(null);

  const refreshSessions = useCallback(async () => {
    try {
      const res = await get<ChatSessionListData>("/chat/sessions");
      if (res.success && res.data) {
        setSessions(res.data.sessions);
      }
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    refreshSessions();
    return () => {
      clientRef.current?.disconnect();
      clientRef.current = null;
    };
  }, [refreshSessions]);

  const loadHistory = useCallback(async (sessionId: string) => {
    const res = await get<ChatMessagesData>(`/chat/sessions/${sessionId}/messages`);
    if (res.success && res.data) {
      setMessages(
        res.data.messages.map((m) => ({
          type: "message",
          content: m.content,
          sender: m.role,
          timestamp: m.created_at ?? "",
          localId: `hist-${m.id}`,
        }))
      );
    } else {
      setMessages([]);
    }
  }, []);

  const connectTo = useCallback(
    (sessionId: string | null) => {
      if (clientRef.current) {
        clientRef.current.disconnect();
      }
      const client = new WsClient(
        (msg) => {
          // The server confirms/creates the session on connect — record it.
          if (msg.type === "connected" && msg.session_id) {
            const sid = msg.session_id;
            setActiveSessionId(sid);
            setSessions((prev) =>
              prev.some((s) => s.id === sid)
                ? prev
                : [
                    {
                      id: sid,
                      title: "WebSocket Chat",
                      tool_id: "chat_tool",
                      created_at: null,
                      updated_at: null,
                    },
                    ...prev,
                  ]
            );
            return;
          }
          setMessages((prev) => [
            ...prev,
            { ...msg, localId: `ws-${localCounter++}` },
          ]);
        },
        setStatus
      );
      clientRef.current = client;
      client.connect(sessionId);
    },
    []
  );

  const handleNewSession = async () => {
    setActiveSessionId(null);
    setMessages([]);
    connectTo(null);
    // The "connected" message carries the freshly-created session id.
  };

  const handleSelectSession = async (sessionId: string) => {
    setActiveSessionId(sessionId);
    setMessages([]);
    await loadHistory(sessionId);
    connectTo(sessionId);
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (!window.confirm("Delete this session and its messages?")) return;
    try {
      await del(`/chat/sessions/${sessionId}`);
    } catch (err) {
      console.warn("Failed to delete session", err);
      return;
    }
    if (activeSessionId === sessionId) {
      clientRef.current?.disconnect();
      setActiveSessionId(null);
      setMessages([]);
    }
    setSessions((prev) => prev.filter((s) => s.id !== sessionId));
  };

  const send = (content: string) => {
    clientRef.current?.send(content);
  };

  return (
    <div className="tool-page">
      <h2>Chat Tool</h2>
      <p>A real-time chat template using WebSocket, with session history and resume.</p>

      <div className="chat-controls">
        <button onClick={handleNewSession} disabled={status === "connected" && !activeSessionId}>
          New Chat
        </button>
        <span className={`ws-status status-${status}`}>{status}</span>
      </div>

      <div className="chat-layout">
        <aside className="chat-sessions">
          <h3>Sessions</h3>
          {loadingSessions && <p className="status-text">Loading...</p>}
          {!loadingSessions && sessions.length === 0 && (
            <p className="status-text">No sessions yet. Start a new chat.</p>
          )}
          <ul>
            {sessions.map((s) => (
              <li key={s.id}>
                <button
                  className={`chat-session-btn${activeSessionId === s.id ? " active" : ""}`}
                  onClick={() => handleSelectSession(s.id)}
                >
                  <span className="chat-session-title">{s.title || "Chat"}</span>
                  <span className="chat-session-date">
                    {s.updated_at
                      ? new Date(s.updated_at).toLocaleString("zh-CN")
                      : ""}
                  </span>
                </button>
                <button
                  className="chat-session-del"
                  aria-label="Delete session"
                  onClick={(e) => handleDeleteSession(e, s.id)}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <div className="chat-main">
          <div className="chat-messages">
            {messages.length === 0 && (
              <p className="status-text">
                {status === "connected"
                  ? "No messages yet — say hello!"
                  : "Click 'New Chat' or pick a session to begin."}
              </p>
            )}
            {messages.map((msg) => (
              <ChatMessage key={msg.localId} message={msg} />
            ))}
          </div>

          <ChatInput onSend={send} disabled={status !== "connected"} />
        </div>
      </div>
    </div>
  );
}
