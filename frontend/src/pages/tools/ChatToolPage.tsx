import { useRef, useState } from "react";
import { WsClient } from "../../lib/ws";
import type { WsMessage } from "../../types";
import ChatMessage from "../../components/chat/ChatMessage";
import ChatInput from "../../components/chat/ChatInput";

export default function ChatToolPage() {
  const [messages, setMessages] = useState<WsMessage[]>([]);
  const [status, setStatus] = useState("disconnected");
  const clientRef = useRef<WsClient | null>(null);

  const connect = () => {
    if (clientRef.current) {
      clientRef.current.disconnect();
    }
    const client = new WsClient(
      "/ws/chat",
      (msg) => setMessages((prev) => [...prev, msg]),
      setStatus
    );
    clientRef.current = client;
    client.connect();
  };

  const send = (content: string) => {
    clientRef.current?.send(content);
  };

  return (
    <div className="tool-page">
      <h2>Chat Tool</h2>
      <p>A real-time chat template using WebSocket.</p>

      <div className="chat-controls">
        <button onClick={connect} disabled={status === "connected"}>
          Connect
        </button>
        <span className={`ws-status status-${status}`}>{status}</span>
      </div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <ChatMessage key={i} message={msg} />
        ))}
      </div>

      <ChatInput onSend={send} disabled={status !== "connected"} />
    </div>
  );
}
