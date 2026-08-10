import type { WsMessage } from "../../types";
import MessageContent from "./MessageContent";

interface Props {
  message: WsMessage;
  /** True while the reply is still streaming — renders plain text (see
   * MessageContent) so per-chunk updates stay cheap and jank-free. */
  plain?: boolean;
}

export default function ChatMessage({ message, plain = false }: Props) {
  // Server error frames are converted to system bubbles before this point,
  // but stay defensive: never render "undefined:" for a malformed frame.
  const sender = message.sender || "系统";
  // CSS classes must be ASCII; the Chinese display label maps to "system".
  const cls = sender === "系统" ? "system" : sender;
  const content = message.content || message.message || "";
  return (
    <div className={`chat-message message-${cls}`}>
      <strong>{sender}:</strong>
      <MessageContent content={content} plain={plain} />
    </div>
  );
}
