import { useEffect, useRef } from "react";
import type { ChatMessage } from "../hooks/useChat";
import { Message } from "./Message";

export function MessageList({ messages }: { messages: ChatMessage[] }) {
  const endRef = useRef<HTMLDivElement>(null);

  // Autoscroll para a última mensagem a cada atualização.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="message-list">
      {messages.map((m) => (
        <Message key={m.id} message={m} />
      ))}
      <div ref={endRef} />
    </div>
  );
}
