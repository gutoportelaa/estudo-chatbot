import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "../hooks/useChat";

export function Message({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  let body: React.ReactNode;
  if (!message.content) {
    body = <span className="typing-dots"><i /><i /><i /></span>;
  } else if (isUser) {
    body = message.content;
  } else if (message.streaming) {
    // Durante o stream: texto plano para evitar markdown parcial quebrado
    body = <span className="streaming-text">{message.content}</span>;
  } else {
    body = (
      <div className="md">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
      </div>
    );
  }

  return (
    <div className={`message ${isUser ? "message-user" : "message-assistant"}`}>
      {!isUser && (
        <span className="message-avatar" aria-hidden>
          <span className="orb orb-sm" />
        </span>
      )}
      <div className="message-bubble">{body}</div>
    </div>
  );
}
