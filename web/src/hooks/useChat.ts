import { useCallback, useEffect, useRef, useState } from "react";
import { fetchMessages, sendMessage, type ChatMessage } from "../api/client";

function uuid(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export type { ChatMessage };

export function useChat(sessionId: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Acumula tokens sem re-render a cada um
  const bufferRef = useRef("");
  const rafRef = useRef<number | null>(null);
  const assistantIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!sessionId) { setMessages([]); return; }
    fetchMessages(sessionId).then((history) => setMessages(history)).catch(() => setMessages([]));
  }, [sessionId]);

  const send = useCallback(
    async (text: string) => {
      if (!sessionId || !text.trim() || isStreaming) return;
      setError(null);

      const userMsg: ChatMessage = { id: uuid(), role: "user", content: text.trim() };
      const assistantId = uuid();
      assistantIdRef.current = assistantId;
      bufferRef.current = "";

      setMessages((prev) => [...prev, userMsg, { id: assistantId, role: "assistant", content: "" }]);
      setIsStreaming(true);

      // Atualiza o state a ~60fps com o conteúdo acumulado no buffer
      const flush = () => {
        const text = bufferRef.current;
        if (text !== null) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantIdRef.current ? { ...m, content: text } : m,
            ),
          );
        }
        rafRef.current = requestAnimationFrame(flush);
      };
      rafRef.current = requestAnimationFrame(flush);

      try {
        await sendMessage(sessionId, text.trim(), (chunk) => {
          bufferRef.current += chunk;
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
        if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
        // Flush final para garantir que o último conteúdo seja renderizado
        const finalText = bufferRef.current;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: finalText } : m,
          ),
        );
        setIsStreaming(false);
      }
    },
    [sessionId, isStreaming],
  );

  return { messages, isStreaming, error, send };
}
