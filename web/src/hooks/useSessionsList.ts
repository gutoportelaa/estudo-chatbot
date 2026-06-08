import { useEffect, useState, useCallback } from "react";
import { fetchSessions, SessionItem } from "../api/client";
import { useAuth } from "./useAuth";

export function useSessionsList() {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const { token } = useAuth();

  const loadSessions = useCallback(async () => {
    if (!token) {
      setSessions([]);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = await fetchSessions();
      setSessions(data);
    } catch (e) {
      console.error("Failed to fetch sessions", e);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const prependSession = useCallback((newSession: SessionItem) => {
    setSessions((prev) => {
      if (prev.find((s) => s.id === newSession.id)) return prev;
      return [newSession, ...prev];
    });
  }, []);

  return { sessions, loading, loadSessions, prependSession };
}
