import { useEffect, useRef } from "react";
import type { ChatMessage } from "../hooks/useChat";
import type { MessageSource } from "../api/client";
import { Message } from "./Message";

export function MessageList({
  messages,
  onOpenSource,
  onOpenSources,
}: {
  messages: ChatMessage[];
  onOpenSource?: (source: MessageSource) => void;
  onOpenSources?: (sources: MessageSource[]) => void;
}) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="message-list">
      {messages.map((m) => (
        <Message
          key={m.id}
          message={m}
          onOpenSource={onOpenSource}
          onOpenSources={onOpenSources}
        />
      ))}
      <div ref={endRef} />
    </div>
  );
}
