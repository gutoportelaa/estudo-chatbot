import { useCallback, useEffect, useSyncExternalStore } from "react";
import {
  getSnapshot,
  loadHistory,
  send as storeSend,
  subscribe,
  type ChatMessage,
} from "./chatStore";

export type { ChatMessage };

const EMPTY = { messages: [] as ChatMessage[], isStreaming: false, error: null as string | null };

/**
 * Assinante fino do `chatStore`. O estado de streaming vive no store de módulo,
 * então navegar entre páginas/sessões nunca interrompe uma geração em curso.
 */
export function useChat(sessionId: string | null) {
  const state = useSyncExternalStore(
    useCallback((cb) => (sessionId ? subscribe(sessionId, cb) : () => {}), [sessionId]),
    () => (sessionId ? getSnapshot(sessionId) : EMPTY),
    () => EMPTY,
  );

  useEffect(() => {
    if (sessionId) void loadHistory(sessionId);
  }, [sessionId]);

  const send = useCallback(
    (text: string) => {
      if (sessionId) void storeSend(sessionId, text);
    },
    [sessionId],
  );

  return {
    messages: state.messages,
    isStreaming: state.isStreaming,
    error: state.error,
    send,
  };
}
