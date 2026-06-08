import { useEffect, useState } from "react";
import { createSession } from "../api/client";

const STORAGE_KEY = "thinkai.session_id";

export function useSession(token: string | null): string | null {
  const [sessionId, setSessionId] = useState<string | null>(() =>
    token ? localStorage.getItem(STORAGE_KEY) : null,
  );

  useEffect(() => {
    if (!token) {
      setSessionId(null);
      return;
    }

    const existing = localStorage.getItem(STORAGE_KEY);
    if (existing) {
      setSessionId(existing);
      return;
    }

    createSession(token)
      .then((session) => {
        localStorage.setItem(STORAGE_KEY, session.id);
        setSessionId(session.id);
      })
      .catch(() => null);
  }, [token]);

  return sessionId;
}
