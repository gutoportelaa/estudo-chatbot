import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
        {!message.content ? (
          <span className="typing-dots"><i /><i /><i /></span>
        ) : isUser ? (
          message.content
        ) : (
          <div className="md">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
