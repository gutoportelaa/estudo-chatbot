import type { ChatMessage } from "../hooks/useChat";

export function Message({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`message ${isUser ? "message-user" : "message-assistant"}`}>
      {!isUser && (
        <span className="message-avatar" aria-hidden>
          <span className="orb orb-sm" />
        </span>
      )}
      <div className="message-bubble">
        {message.content || <span className="typing-dots"><i /><i /><i /></span>}
      </div>
    </div>
  );
}
