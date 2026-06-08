import { useEffect, useState } from "react";
import { createSession, fetchMessages } from "../api/client";

const STORAGE_KEY = "thinkai.session_id";

export function useSession(token: string | null): string | null {
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setSessionId(null);
      return;
    }

    const stored = localStorage.getItem(STORAGE_KEY);

    const initSession = async () => {
      if (stored) {
        // Verifica se a sessão ainda existe no servidor
        const messages = await fetchMessages(token, stored).catch(() => null);
        if (messages !== null) {
          setSessionId(stored);
          return;
        }
        // Sessão inválida ou de outro usuário — descarta
        localStorage.removeItem(STORAGE_KEY);
      }

      // Cria nova sessão
      const session = await createSession(token).catch(() => null);
      if (session) {
        localStorage.setItem(STORAGE_KEY, session.id);
        setSessionId(session.id);
      }
    };

    initSession();
  }, [token]);

  return sessionId;
}
