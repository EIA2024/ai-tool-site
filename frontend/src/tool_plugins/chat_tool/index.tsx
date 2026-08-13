import { useCallback, useEffect, useRef, useState, type MouseEvent } from "react";
import { get } from "../../lib/api";
import type {
  PublicConfig,
  RealtimeConnection,
  RealtimeServerEvent,
  ToolPluginProps,
} from "../../types";
import ChatInput from "./ChatInput";
import ChatMessage from "./ChatMessage";
import type {
  ChatMessage as ApiChatMessage,
  ChatSession,
  SendMessageData,
} from "./types";

interface UiMessage {
  localId: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  /** True only while this assistant reply is still streaming. */
  streaming?: boolean;
}

let localCounter = 0;

export default function ChatToolPlugin({ client }: ToolPluginProps) {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [status, setStatus] = useState<"connecting" | "connected" | "disconnected" | "error">(
    "connecting"
  );
  const [typing, setTyping] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [models, setModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  // Transient per-session key — blank uses the server .env key.
  const [sessionApiKey, setSessionApiKey] = useState("");

  const connRef = useRef<RealtimeConnection | null>(null);
  const activeSessionIdRef = useRef<string | null>(null);
  const streamingRef = useRef<{ id: string; text: string } | null>(null);
  const historyTokenRef = useRef(0);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const stickToBottomRef = useRef(true);

  const setActive = useCallback((id: string | null) => {
    activeSessionIdRef.current = id;
    setActiveSessionId(id);
  }, []);

  const refreshSessions = useCallback(async () => {
    try {
      const res = await client.invoke<{ sessions: ChatSession[] }>("list_sessions", {
        limit: 50,
      });
      if (res.success && res.data) setSessions(res.data.sessions);
    } finally {
      setLoadingSessions(false);
    }
  }, [client]);

  // Models come from the Host's /api/config — the single source of truth.
  useEffect(() => {
    get<PublicConfig>("/config")
      .then((res) => {
        if (res.success && res.data) {
          setModels(res.data.models);
          setSelectedModel(res.data.default_model);
        }
      })
      .catch(() => {
        /* leave the selector empty on config failure */
      });
  }, []);

  const loadHistory = useCallback(
    async (sessionId: string) => {
      const token = ++historyTokenRef.current;
      const res = await client.invoke<{ messages: ApiChatMessage[] }>("list_messages", {
        session_id: sessionId,
      });
      if (token !== historyTokenRef.current) return; // a newer switch won — drop stale data
      if (res.success && res.data) {
        setMessages(
          res.data.messages.map((m) => ({
            localId: `hist-${m.id}`,
            role: m.role,
            content: m.content,
            timestamp: m.created_at ?? "",
          }))
        );
      } else {
        setMessages([]);
      }
    },
    [client]
  );

  const handleEvent = useCallback(
    (event: RealtimeServerEvent) => {
      if (event.type === "progress") {
        setTyping(true);
        const sid = event.data.session_id;
        if (typeof sid === "string" && sid && !activeSessionIdRef.current) setActive(sid);
        return;
      }
      if (event.type === "delta") {
        setTyping(false);
        const text = typeof event.data.content === "string" ? event.data.content : "";
        if (streamingRef.current) {
          streamingRef.current.text += text;
          const { id, text: full } = streamingRef.current;
          setMessages((prev) =>
            prev.map((m) => (m.localId === id ? { ...m, content: full, streaming: true } : m))
          );
        } else {
          const id = `stream-${localCounter++}`;
          streamingRef.current = { id, text };
          setMessages((prev) => [
            ...prev,
            { localId: id, role: "assistant", content: text, timestamp: new Date().toISOString(), streaming: true },
          ]);
        }
        return;
      }
      if (event.type === "result") {
        setTyping(false);
        const data = event.data as unknown as SendMessageData;
        const content = data.message?.content ?? "";
        if (data.session_id) setActive(data.session_id);
        if (streamingRef.current) {
          const id = streamingRef.current.id;
          streamingRef.current = null;
          setMessages((prev) =>
            prev.map((m) => (m.localId === id ? { ...m, content, streaming: false } : m))
          );
        } else {
          setMessages((prev) => [
            ...prev,
            { localId: `ws-${localCounter++}`, role: "assistant", content, timestamp: new Date().toISOString() },
          ]);
        }
        // The server may have auto-titled this session from its first message.
        refreshSessions();
        return;
      }
      if (event.type === "error") {
        setTyping(false);
        setMessages((prev) => [
          ...prev,
          {
            localId: `sys-${localCounter++}`,
            role: "system",
            content: event.data.message || "发生错误",
            timestamp: new Date().toISOString(),
          },
        ]);
      }
    },
    [refreshSessions, setActive]
  );

  useEffect(() => {
    refreshSessions();
    const conn = client.connect("send_message");
    conn.onEvent(handleEvent);
    conn.onStatus(setStatus);
    conn.open();
    connRef.current = conn;
    return () => {
      conn.close();
      connRef.current = null;
    };
  }, [client, refreshSessions, handleEvent]);

  // Auto-scroll as new messages/chunks arrive, but never yank the user away
  // while they scroll up through history.
  useEffect(() => {
    if (!stickToBottomRef.current) return;
    const raf = requestAnimationFrame(() => {
      const el = messagesRef.current;
      if (el && stickToBottomRef.current) el.scrollTop = el.scrollHeight;
    });
    return () => cancelAnimationFrame(raf);
  }, [messages, typing]);

  const handleMessagesScroll = () => {
    const el = messagesRef.current;
    if (!el) return;
    stickToBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  };

  const handleNewSession = () => {
    setActive(null);
    setMessages([]);
    setTyping(false);
    streamingRef.current = null;
    if (!connRef.current?.isOpen) connRef.current?.open();
  };

  const handleSelectSession = async (sessionId: string) => {
    setActive(sessionId);
    setMessages([]);
    setTyping(false);
    streamingRef.current = null;
    await loadHistory(sessionId);
    if (!connRef.current?.isOpen) connRef.current?.open();
  };

  const handleDeleteSession = async (event: MouseEvent<HTMLButtonElement>, sessionId: string) => {
    event.stopPropagation();
    if (!window.confirm("Delete this session and its messages?")) return;
    try {
      await client.invoke("delete_session", { session_id: sessionId });
    } catch (err) {
      console.warn("Failed to delete session", err);
      return;
    }
    if (activeSessionIdRef.current === sessionId) {
      setActive(null);
      setMessages([]);
      setTyping(false);
      streamingRef.current = null;
    }
    setSessions((prev) => prev.filter((s) => s.id !== sessionId));
  };

  const send = (content: string) => {
    if (status !== "connected") return;
    setMessages((prev) => [
      ...prev,
      { localId: `local-${localCounter++}`, role: "user", content, timestamp: new Date().toISOString() },
    ]);
    const payload: Record<string, unknown> = { content };
    if (selectedModel) payload.model = selectedModel;
    if (activeSessionIdRef.current) payload.session_id = activeSessionIdRef.current;
    if (sessionApiKey) payload.session_api_key = sessionApiKey;
    connRef.current?.send(payload);
  };

  return (
    <div className="tool-page">
      <h2>Chat Tool</h2>
      <p>A real-time chat tool with streamed AI responses, session history and resume.</p>

      <div className="chat-controls">
        <button onClick={handleNewSession}>New Chat</button>
        {models.length > 0 && (
          <select
            className="chat-model-select"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            aria-label="Model"
          >
            {models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        )}
        <input
          className="chat-key-input"
          type="password"
          autoComplete="off"
          placeholder="临时 Key（留空用服务器 .env）"
          value={sessionApiKey}
          onChange={(e) => setSessionApiKey(e.target.value)}
          aria-label="Session API key"
        />
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
                    {s.updated_at ? new Date(s.updated_at).toLocaleString("zh-CN") : ""}
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
          <div className="chat-messages" ref={messagesRef} onScroll={handleMessagesScroll}>
            {messages.length === 0 && (
              <p className="status-text">
                {status === "connected"
                  ? "No messages yet — say hello!"
                  : "Click 'New Chat' or pick a session to begin."}
              </p>
            )}
            {messages.map((msg) => (
              <ChatMessage key={msg.localId} role={msg.role} content={msg.content} plain={msg.streaming} />
            ))}
            {typing && (
              <div className="chat-typing">
                <span className="dot" />
                <span className="dot" />
                <span className="dot" />
              </div>
            )}
          </div>

          <ChatInput onSend={send} disabled={status !== "connected"} />
        </div>
      </div>
    </div>
  );
}
