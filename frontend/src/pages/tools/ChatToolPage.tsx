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
  const [typing, setTyping] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const clientRef = useRef<WsClient | null>(null);
  // Incremented on every session switch; stale async responses (history
  // fetches from a previous session resolving after the user clicked another)
  // check it and drop themselves.
  const historyTokenRef = useRef(0);
  // The in-flight streaming reply: the localId of the assistant bubble we are
  // accumulating "chunk" frames into plus its text so far. Cleared when the
  // final "message" frame lands, on disconnect, and on session switch.
  const streamingRef = useRef<{ id: string; text: string } | null>(null);

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
    const token = ++historyTokenRef.current;
    const res = await get<ChatMessagesData>(`/chat/sessions/${sessionId}/messages`);
    if (token !== historyTokenRef.current) return; // a newer switch won — drop stale data
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

  const handleStatus = useCallback((s: string) => {
    // A reply was in flight when the socket dropped — clear the typing dots
    // (or they'd spin forever) and drop the half-streamed reply reference.
    if (s === "disconnected" || s.startsWith("reconnecting")) {
      setTyping(false);
      streamingRef.current = null;
    }
    setStatus(s);
  }, []);

  const connectTo = useCallback(
    (sessionId: string | null) => {
      if (clientRef.current) {
        clientRef.current.disconnect();
      }
      const client = new WsClient(
        (msg) => {
          if (msg.type === "connected") {
            // Fresh handshake — any half-streamed reply from the previous
            // connection is done; start clean.
            streamingRef.current = null;
            if (!msg.session_id) return;
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
          if (msg.type === "typing") {
            setTyping(true);
            return;
          }
          if (msg.type === "chunk") {
            // Streamed deltas of the assistant reply. Append to the open
            // streaming bubble, or open one on the first chunk.
            setTyping(false);
            const text = msg.content ?? "";
            if (streamingRef.current) {
              streamingRef.current.text += text;
              const { id, text: full } = streamingRef.current;
              setMessages((prev) =>
                prev.map((m) => (m.localId === id ? { ...m, content: full } : m))
              );
            } else {
              const id = `stream-${localCounter++}`;
              streamingRef.current = { id, text };
              setMessages((prev) => [
                ...prev,
                {
                  type: "message",
                  content: text,
                  sender: "assistant",
                  timestamp: new Date().toISOString(),
                  localId: id,
                },
              ]);
            }
            return;
          }
          // Error frames (empty content, too long, rate-limited) have no
          // sender/content — surface them as a clear system bubble rather
          // than a malformed "undefined:" one.
          if (msg.type === "error") {
            setTyping(false);
            setMessages((prev) => [
              ...prev,
              {
                type: "message",
                content: msg.message || "发生错误",
                sender: "系统",
                timestamp: new Date().toISOString(),
                localId: `sys-${localCounter++}`,
              },
            ]);
            return;
          }
          if (msg.type === "message") {
            setTyping(false);
            if (streamingRef.current) {
              // Final "message" frame closes the streaming reply — replace
              // the accumulated chunk text with the full reply the server
              // persisted (history reload shows the exact same text).
              const id = streamingRef.current.id;
              streamingRef.current = null;
              setMessages((prev) =>
                prev.map((m) => (m.localId === id ? { ...m, content: msg.content ?? "" } : m))
              );
            } else {
              // No preceding chunks (e.g. a failure-path reply) — append.
              setMessages((prev) => [
                ...prev,
                { ...msg, localId: `ws-${localCounter++}` },
              ]);
            }
          }
        },
        handleStatus
      );
      clientRef.current = client;
      client.connect(sessionId);
    },
    [handleStatus]
  );

  const handleNewSession = async () => {
    setActiveSessionId(null);
    setMessages([]);
    setTyping(false);
    streamingRef.current = null;
    connectTo(null);
    // The "connected" message carries the freshly-created session id.
  };

  const handleSelectSession = async (sessionId: string) => {
    setActiveSessionId(sessionId);
    setMessages([]);
    setTyping(false);
    streamingRef.current = null;
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
      setTyping(false);
      streamingRef.current = null;
    }
    setSessions((prev) => prev.filter((s) => s.id !== sessionId));
  };

  const send = (content: string) => {
    if (status !== "connected") return;
    // Show the user's message immediately; the server only streams back the
    // assistant reply, so without this optimistic bubble the user's own text
    // would stay invisible until a history reload.
    setMessages((prev) => [
      ...prev,
      {
        type: "message",
        content,
        sender: "user",
        timestamp: new Date().toISOString(),
        localId: `local-${localCounter++}`,
      },
    ]);
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
