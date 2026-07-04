import { useEffect, useRef } from "react";
import type { ChatMessage } from "../hooks/useChat";
import type { MessageSource } from "../api/client";
import { Message } from "./Message";

export function MessageList({
  messages,
  onOpenSource,
}: {
  messages: ChatMessage[];
  onOpenSource?: (source: MessageSource) => void;
}) {
  const endRef = useRef<HTMLDivElement>(null);

  // Autoscroll para a última mensagem a cada atualização.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="message-list">
      {messages.map((m) => (
        <Message key={m.id} message={m} onOpenSource={onOpenSource} />
      ))}
      <div ref={endRef} />
    </div>
  );
}
