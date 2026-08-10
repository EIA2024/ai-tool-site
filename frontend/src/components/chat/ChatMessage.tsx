import type { WsMessage } from "../../types";
import MessageContent from "./MessageContent";

interface Props {
  message: WsMessage;
}

export default function ChatMessage({ message }: Props) {
  // Server error frames are converted to system bubbles before this point,
  // but stay defensive: never render "undefined:" for a malformed frame.
  const sender = message.sender || "系统";
  // CSS classes must be ASCII; the Chinese display label maps to "system".
  const cls = sender === "系统" ? "system" : sender;
  const content = message.content || message.message || "";
  return (
    <div className={`chat-message message-${cls}`}>
      <strong>{sender}:</strong>
      <MessageContent content={content} />
    </div>
  );
}
