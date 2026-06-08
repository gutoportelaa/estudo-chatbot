import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  createSession,
  deleteSession,
  listSessions,
  type SessionSummary,
} from "../api/client";

function storageKey(userId: string | null): string {
  return `thinkai.active_session_id:${userId ?? "anonymous"}`;
}

export function useSessions(userId: string | null, enabled: boolean) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const key = useMemo(() => storageKey(userId), [userId]);

  const refresh = useCallback(async () => {
    if (!enabled) return;

    setIsLoading(true);
    setError(null);

    try {
      const items = await listSessions();
      setSessions(items);

      const saved = localStorage.getItem(key);
      const preferred = saved && items.some((session) => session.id === saved)
        ? saved
        : items[0]?.id ?? null;

      if (preferred) {
        setActiveSessionId(preferred);
        localStorage.setItem(key, preferred);
      } else {
        const createdId = await createSession();
        const next = [{ id: createdId } satisfies SessionSummary];
        setSessions(next);
        setActiveSessionId(createdId);
        localStorage.setItem(key, createdId);
      }
    } catch (error_) {
      if (error_ instanceof ApiError && (error_.status === 404 || error_.status === 405)) {
        try {
          const createdId = await createSession();
          const next = [{ id: createdId } satisfies SessionSummary];
          setSessions(next);
          setActiveSessionId(createdId);
          localStorage.setItem(key, createdId);
          setError(null);
          return;
        } catch (fallbackError) {
          setError(
            fallbackError instanceof Error
              ? fallbackError.message
              : "Falha ao carregar sessões",
          );
          return;
        }
      }

      setError(error_ instanceof Error ? error_.message : "Falha ao carregar sessões");
    } finally {
      setIsLoading(false);
    }
  }, [enabled, key]);

  useEffect(() => {
    if (!enabled) {
      setSessions([]);
      setActiveSessionId(null);
      setError(null);
      return;
    }

    const saved = localStorage.getItem(key);
    if (saved) {
      setActiveSessionId(saved);
    }

    void refresh();
  }, [enabled, key, refresh]);

  useEffect(() => {
    if (!enabled || !activeSessionId) return;
    localStorage.setItem(key, activeSessionId);
  }, [activeSessionId, enabled, key]);

  const selectSession = useCallback(
    (sessionId: string) => {
      setActiveSessionId(sessionId);
      localStorage.setItem(key, sessionId);
    },
    [key],
  );

  const createNewSession = useCallback(async () => {
    const sessionId = await createSession();
    setSessions((current) => [{ id: sessionId }, ...current]);
    setActiveSessionId(sessionId);
    localStorage.setItem(key, sessionId);
    return sessionId;
  }, [key]);

  const removeSession = useCallback(
    async (sessionId: string) => {
      await deleteSession(sessionId);
      setSessions((current) => current.filter((session) => session.id !== sessionId));

      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
      }
    },
    [activeSessionId],
  );

  return {
    sessions,
    activeSessionId,
    setActiveSessionId: selectSession,
    createNewSession,
    removeSession,
    refresh,
    isLoading,
    error,
  };
}