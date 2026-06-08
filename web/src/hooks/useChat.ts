import { useCallback, useEffect, useState } from "react";
import { fetchMessages, sendMessage } from "../api/client";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export function useChat(token: string | null, sessionId: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !sessionId) {
      setMessages([]);
      return;
    }
    fetchMessages(token, sessionId).then((history) => {
      setMessages(history.map((m) => ({ id: m.id, role: m.role, content: m.content })));
    });
  }, [token, sessionId]);

  const send = useCallback(
    async (text: string) => {
      if (!token || !sessionId || !text.trim() || isStreaming) return;
      setError(null);

      const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", content: text.trim() };
      const assistantId = crypto.randomUUID();
      setMessages((prev) => [...prev, userMsg, { id: assistantId, role: "assistant", content: "" }]);
      setIsStreaming(true);

      try {
        await sendMessage(token, sessionId, text.trim(), (chunk) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + chunk } : m)),
          );
        });
      } catch {
        setError("Não foi possível obter resposta. Verifique se a API está ativa.");
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId && m.content === ""
              ? { ...m, content: "⚠️ Erro ao gerar resposta." }
              : m,
          ),
        );
      } finally {
        setIsStreaming(false);
      }
    },
    [token, sessionId, isStreaming],
  );

  return { messages, isStreaming, error, send };
}
