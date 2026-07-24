import type { WsMessage } from "../../types";

interface Props {
  message: WsMessage;
}

export default function ChatMessage({ message }: Props) {
  return (
    <div className={`chat-message message-${message.sender}`}>
      <strong>{message.sender}:</strong> {message.content}
    </div>
  );
}
