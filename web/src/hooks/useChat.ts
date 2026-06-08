import { useCallback, useEffect, useState } from "react";
import { fetchHistory, streamChat } from "../api/client";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export function useChat(sessionId: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Recarrega o histórico persistido ao (re)abrir a sessão.
  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }

    fetchHistory(sessionId)
      .then((history) => {
        setMessages(
          history.map((m, i) => ({ id: `h${i}`, role: m.role, content: m.content })),
        );
      })
      .catch(() => {
        setMessages([]);
      });
  }, [sessionId]);

  const send = useCallback(
    async (text: string) => {
      if (!sessionId || !text.trim() || isStreaming) return;
      setError(null);

      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: text.trim(),
      };
      const assistantId = crypto.randomUUID();
      setMessages((prev) => [
        ...prev,
        userMsg,
        { id: assistantId, role: "assistant", content: "" },
      ]);
      setIsStreaming(true);

      try {
        await streamChat(sessionId, text.trim(), (token) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + token } : m,
            ),
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
