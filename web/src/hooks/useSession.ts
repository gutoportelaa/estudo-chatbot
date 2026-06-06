import { useEffect, useState } from "react";
import { createSession } from "../api/client";

const STORAGE_KEY = "thinkai.session_id";

/** Cria ou recupera o ID de sessão do usuário, persistido em localStorage. */
export function useSession(): string | null {
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    const existing = localStorage.getItem(STORAGE_KEY);
    if (existing) {
      setSessionId(existing);
      return;
    }
    createSession()
      .then((id) => {
        localStorage.setItem(STORAGE_KEY, id);
        setSessionId(id);
      })
      .catch(() => {
        // Fallback offline: gera um UUID local caso a API esteja indisponível.
        const id = crypto.randomUUID();
        localStorage.setItem(STORAGE_KEY, id);
        setSessionId(id);
      });
  }, []);

  return sessionId;
}
