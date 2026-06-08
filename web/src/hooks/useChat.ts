import { useCallback, useEffect, useState } from "react";
import { fetchMessages, sendMessage, type ChatMessage } from "../api/client";

export function useChat(sessionId: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) { setMessages([]); return; }
    fetchMessages(sessionId).then((history) => setMessages(history)).catch(() => setMessages([]));
  }, [sessionId]);

  const send = useCallback(
    async (text: string) => {
      if (!sessionId || !text.trim() || isStreaming) return;
      setError(null);

      const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", content: text.trim() };
      const assistantId = crypto.randomUUID();
      setMessages((prev) => [...prev, userMsg, { id: assistantId, role: "assistant", content: "" }]);
      setIsStreaming(true);

      try {
        await sendMessage(sessionId, text.trim(), (chunk) => {
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
    [sessionId, isStreaming],
  );

  return { messages, isStreaming, error, send };
}
