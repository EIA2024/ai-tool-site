import { useEffect, useRef, useState } from "react";

interface Props {
  onSend: (text: string) => void;
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: Props) {
  const [text, setText] = useState("");
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  // Grow the textarea to fit its content (bounded by CSS max-height, beyond
  // which it scrolls internally) so multi-line prompts/code stay visible.
  // Running on every commit (not in the event handlers) means it also shrinks
  // back when the value clears after sending — a requestAnimationFrame there
  // would race React applying the empty value and leave the box oversized.
  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${ta.scrollHeight}px`;
  }, [text]);

  const handleSubmit = () => {
    if (!text.trim()) return;
    onSend(text.trim());
    setText("");
  };

  return (
    <div className="chat-input">
      <textarea
        ref={taRef}
        value={text}
        rows={1}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          // Enter sends — but never while an IME composition is active
          // (pressing Enter to confirm a Chinese candidate must not send),
          // and Shift+Enter inserts a newline instead.
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            handleSubmit();
          }
        }}
        placeholder={
          disabled
            ? "Connect to start chatting..."
            : "Type a message... (Enter to send, Shift+Enter for newline)"
        }
        disabled={disabled}
        aria-label="Chat message"
      />
      <button onClick={handleSubmit} disabled={disabled || !text.trim()}>
        Send
      </button>
    </div>
  );
}
