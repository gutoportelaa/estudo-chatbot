import { useCallback, useEffect, useState } from "react";
import {
  createSession,
  deleteSession,
  listSessions,
  renameSession,
  type SessionSummary,
} from "../api/client";
import { dropSession } from "./chatStore";

/**
 * useSessions — CRUD leve sobre a lista de sessões do usuário.
 *
 * Sem estado de "sessão ativa": quem determina a ativa é a URL (`/chat/:sessionId`).
 * As páginas que precisam do id lêem via `useParams` do react-router.
 */
export function useSessions(enabled: boolean) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setIsLoading(true);
    setError(null);
    try {
      setSessions(await listSessions());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar sessões");
    } finally {
      setIsLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) {
      setSessions([]);
      setError(null);
      return;
    }
    void refresh();
  }, [enabled, refresh]);

  const createNewSession = useCallback(async (documentIds: string[] = []): Promise<string> => {
    const sessionId = await createSession(documentIds);
    setSessions((current) => [{ id: sessionId }, ...current]);
    return sessionId;
  }, []);

  const removeSession = useCallback(async (sessionId: string) => {
    await deleteSession(sessionId);
    dropSession(sessionId);
    setSessions((current) => current.filter((s) => s.id !== sessionId));
  }, []);

  const updateSessionTitle = useCallback(async (sessionId: string, title: string) => {
    await renameSession(sessionId, title);
    await refresh();
  }, [refresh]);

  return {
    sessions,
    refresh,
    createNewSession,
    updateSessionTitle,
    removeSession,
    isLoading,
    error,
  };
}
