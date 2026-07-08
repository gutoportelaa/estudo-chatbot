import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useSessions } from "../hooks/useSessions";

interface Props {
  isAuthenticated: boolean;
}

/**
 * Rota /chat sem sessionId: cria uma sessão nova e redireciona pra /chat/:id.
 * StrictMode roda o efeito duas vezes em dev — o ref evita criar duas sessões.
 */
export function AutoCreateChatSession({ isAuthenticated }: Props) {
  const navigate = useNavigate();
  const { createNewSession } = useSessions(isAuthenticated);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      try {
        const id = await createNewSession();
        navigate(`/chat/${id}`, { replace: true });
      } catch {
        navigate("/inicio", { replace: true });
      }
    })();
  }, [createNewSession, navigate]);

  return (
    <main className="content is-empty">
      <div className="welcome">
        <div className="orb" />
        <h1 className="greeting-title">Criando conversa…</h1>
      </div>
    </main>
  );
}
