import { useCallback, useEffect, useState } from "react";
import { fetchHistory, streamChat } from "../api/client";
import { useAuth } from "./useAuth";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export function useChat(sessionId: string | null, onNewSessionCreated?: () => void) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { token } = useAuth();
  
  // Controle para saber se já fomos buscar histórico para esse sessionId
  const [loadedSessionId, setLoadedSessionId] = useState<string | null>(null);

  // Recarrega o histórico persistido ao (re)abrir a sessão.
  useEffect(() => {
    if (!sessionId || !token) {
      setMessages([]);
      return;
    }
    
    // Evita loop ou flash se for a mesma sessão
    if (loadedSessionId === sessionId) return;

    fetchHistory(sessionId).then((history) => {
      if (Array.isArray(history)) {
        setMessages(
          history.map((m, i) => ({ id: `h${i}`, role: m.role, content: m.content })),
        );
      }
      setLoadedSessionId(sessionId);
    }).catch(() => {
      // Falha ao carregar (provavelmente uma sessão local/nova que ainda não existe no back)
      setMessages([]);
      setLoadedSessionId(sessionId);
    });
  }, [sessionId, token, loadedSessionId]);

  const send = useCallback(
    async (text: string) => {
      if (!sessionId || !text.trim() || isStreaming) return;
      setError(null);

      const isFirstMessage = messages.length === 0;

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
        await streamChat(sessionId, text.trim(), (tokenStr) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + tokenStr } : m,
            ),
          );
        });
        
        if (isFirstMessage && onNewSessionCreated) {
           onNewSessionCreated();
        }
      } catch {
        setError("Não foi possível enviar a mensagem.");
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
    [sessionId, isStreaming, messages.length, onNewSessionCreated],
  );

  return { messages, isStreaming, error, send };
}
