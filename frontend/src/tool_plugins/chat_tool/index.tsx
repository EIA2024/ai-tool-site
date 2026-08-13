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

interface PendingRequest {
  sessionId: string | null;
  viewToken: number;
  streaming: { id: string; text: string } | null;
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
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  // Transient per-session key — blank uses the server .env key.
  const [sessionApiKey, setSessionApiKey] = useState("");

  const connRef = useRef<RealtimeConnection | null>(null);
  const activeSessionIdRef = useRef<string | null>(null);
  const requestsRef = useRef(new Map<string, PendingRequest>());
  const historyTokenRef = useRef(0);
  const sessionsTokenRef = useRef(0);
  const viewTokenRef = useRef(0);
  const mountedRef = useRef(true);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const stickToBottomRef = useRef(true);

  const setActive = useCallback((id: string | null) => {
    activeSessionIdRef.current = id;
    setActiveSessionId(id);
  }, []);

  const refreshSessions = useCallback(async () => {
    const token = ++sessionsTokenRef.current;
    setLoadingSessions(true);
    setSessionsError(null);
    try {
      const res = await client.invoke<{ sessions: ChatSession[] }>("list_sessions", {
        limit: 50,
      });
      if (token !== sessionsTokenRef.current || !mountedRef.current) return;
      if (res.success && res.data) {
        setSessions(res.data.sessions);
      } else {
        setSessionsError(res.error?.message ?? "Failed to load sessions.");
      }
    } catch {
      if (token === sessionsTokenRef.current && mountedRef.current) {
        setSessionsError("Failed to load sessions.");
      }
    } finally {
      if (token === sessionsTokenRef.current && mountedRef.current) {
        setLoadingSessions(false);
      }
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
      setHistoryError(null);
      try {
        const res = await client.invoke<{ messages: ApiChatMessage[] }>("list_messages", {
          session_id: sessionId,
        });
        if (token !== historyTokenRef.current || !mountedRef.current) return;
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
          setHistoryError(res.error?.message ?? "Failed to load messages.");
        }
      } catch {
        if (token === historyTokenRef.current && mountedRef.current) {
          setHistoryError("Failed to load messages.");
        }
      }
    },
    [client]
  );

  const handleEvent = useCallback(
    (event: RealtimeServerEvent) => {
      if (event.type === "ready") return;
      const request = event.request_id ? requestsRef.current.get(event.request_id) : undefined;
      if (!request) {
        if (event.type === "error" && event.request_id === null) {
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
        return;
      }

      if (event.type === "progress") {
        const sid = event.data.session_id;
        if (typeof sid === "string" && sid) {
          request.sessionId = sid;
          if (
            request.viewToken === viewTokenRef.current &&
            activeSessionIdRef.current === null
          ) {
            setActive(sid);
          }
        }
        if (request.sessionId === activeSessionIdRef.current) setTyping(true);
        return;
      }

      const belongsToActiveView =
        request.sessionId !== null
          ? request.sessionId === activeSessionIdRef.current
          : request.viewToken === viewTokenRef.current && activeSessionIdRef.current === null;

      if (event.type === "delta") {
        if (!belongsToActiveView) return;
        setTyping(false);
        const text = typeof event.data.content === "string" ? event.data.content : "";
        if (request.streaming) {
          request.streaming.text += text;
          const { id, text: full } = request.streaming;
          setMessages((prev) =>
            prev.map((m) => (m.localId === id ? { ...m, content: full, streaming: true } : m))
          );
        } else {
          const id = `stream-${localCounter++}`;
          request.streaming = { id, text };
          setMessages((prev) => [
            ...prev,
            { localId: id, role: "assistant", content: text, timestamp: new Date().toISOString(), streaming: true },
          ]);
        }
        return;
      }
      if (event.type === "result") {
        const data = event.data as unknown as SendMessageData;
        const content = data.message?.content ?? "";
        const resultBelongsToActiveView = data.session_id
          ? data.session_id === activeSessionIdRef.current ||
            (request.sessionId === null &&
              request.viewToken === viewTokenRef.current &&
              activeSessionIdRef.current === null)
          : belongsToActiveView;
        if (data.session_id && request.sessionId === null) {
          request.sessionId = data.session_id;
          if (resultBelongsToActiveView && activeSessionIdRef.current === null) {
            setActive(data.session_id);
          }
        }
        if (resultBelongsToActiveView) {
          setTyping(false);
          if (request.streaming) {
            const id = request.streaming.id;
            request.streaming = null;
            setMessages((prev) =>
              prev.map((m) => (m.localId === id ? { ...m, content, streaming: false } : m))
            );
          } else {
            setMessages((prev) => [
              ...prev,
              { localId: `ws-${localCounter++}`, role: "assistant", content, timestamp: new Date().toISOString() },
            ]);
          }
        }
        requestsRef.current.delete(event.request_id);
        // The server may have auto-titled this session from its first message.
        void refreshSessions();
        return;
      }
      if (event.type === "error") {
        requestsRef.current.delete(event.request_id ?? "");
        if (belongsToActiveView) {
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
      }
    },
    [refreshSessions, setActive]
  );

  useEffect(() => {
    mountedRef.current = true;
    void refreshSessions();
    const conn = client.connect("send_message");
    conn.onEvent(handleEvent);
    conn.onStatus(setStatus);
    conn.open();
    connRef.current = conn;
    const requests = requestsRef.current;
    return () => {
      mountedRef.current = false;
      historyTokenRef.current += 1;
      sessionsTokenRef.current += 1;
      viewTokenRef.current += 1;
      requests.clear();
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
    historyTokenRef.current += 1;
    viewTokenRef.current += 1;
    setActive(null);
    setMessages([]);
    setHistoryError(null);
    setTyping(false);
    requestsRef.current.forEach((request) => {
      request.streaming = null;
    });
    if (!connRef.current?.isOpen) connRef.current?.open();
  };

  const handleSelectSession = (sessionId: string) => {
    viewTokenRef.current += 1;
    setActive(sessionId);
    setMessages([]);
    setHistoryError(null);
    setTyping(false);
    requestsRef.current.forEach((request) => {
      request.streaming = null;
    });
    void loadHistory(sessionId);
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
      historyTokenRef.current += 1;
      viewTokenRef.current += 1;
      setActive(null);
      setMessages([]);
      setHistoryError(null);
      setTyping(false);
      requestsRef.current.forEach((request) => {
        request.streaming = null;
      });
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
    const requestId = connRef.current?.send(payload);
    if (requestId) {
      requestsRef.current.set(requestId, {
        sessionId: activeSessionIdRef.current,
        viewToken: viewTokenRef.current,
        streaming: null,
      });
    }
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
          {!loadingSessions && sessionsError && (
            <div className="status-text" role="alert">
              <p>{sessionsError}</p>
              <button onClick={() => void refreshSessions()}>Retry sessions</button>
            </div>
          )}
          {!loadingSessions && !sessionsError && sessions.length === 0 && (
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
            {historyError && (
              <div className="status-text" role="alert">
                <p>{historyError}</p>
                <button
                  onClick={() => {
                    if (activeSessionIdRef.current) void loadHistory(activeSessionIdRef.current);
                  }}
                >
                  Retry messages
                </button>
              </div>
            )}
            {!historyError && messages.length === 0 && (
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
