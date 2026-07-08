import { useState } from "react";
import { NavLink, useNavigate, useParams } from "react-router-dom";
import { useAppUI } from "../context/AppUIContext";
import { useSessions } from "../hooks/useSessions";
import { ArrowLeftIcon, ChatIcon, EllipsisIcon, PlusIcon, TrashIcon } from "./icons";
import { SidebarFooter } from "./SidebarFooter";

interface Props {
  isAuthenticated: boolean;
}

export function SidebarChat({ isAuthenticated }: Props) {
  const ui = useAppUI();
  const navigate = useNavigate();
  const params = useParams<{ sessionId: string }>();
  const activeId = params.sessionId ?? null;
  const { sessions, createNewSession, removeSession, updateSessionTitle } =
    useSessions(isAuthenticated);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  const onNewChat = async () => {
    try {
      const id = await createNewSession();
      navigate(`/chat/${id}`);
    } catch {
      /* silencioso */
    }
  };

  const onRename = async (id: string, currentTitle: string | null | undefined) => {
    const label = currentTitle?.trim() || "Conversa sem título";
    const next = window.prompt("Novo nome da conversa", label);
    if (next === null) return;
    const trimmed = next.trim();
    if (!trimmed) return;
    await updateSessionTitle(id, trimmed);
  };

  const onDelete = async (id: string) => {
    const session = sessions.find((s) => s.id === id);
    const label = session?.title?.trim() || "esta conversa";
    if (!window.confirm(`Apagar ${label}? Essa ação não pode ser desfeita.`)) return;
    await removeSession(id);
    if (id === activeId) {
      const remaining = sessions.filter((s) => s.id !== id);
      if (remaining.length === 0) navigate("/inicio");
      else navigate(`/chat/${remaining[0].id}`);
    }
  };

  return (
    <aside
      className={`sidebar${ui.sidebarOpen ? "" : " is-collapsed"}`}
      aria-label="Conversas"
    >
      <div className="sidebar-inner">
        <button
          className="sidebar-new-btn"
          onClick={() => void onNewChat()}
          title="Nova conversa"
        >
          <PlusIcon />
          <span>Nova conversa</span>
        </button>

        <button
          className="sidebar-back-btn"
          onClick={() => navigate("/inicio")}
          title="Voltar ao início"
        >
          <ArrowLeftIcon />
          <span>Voltar ao início</span>
        </button>

        <nav className="sidebar-sessions">
          {sessions.length === 0 ? (
            <p className="sidebar-empty">Nenhuma sessão ainda</p>
          ) : (
            sessions.map((session, index) => (
              <div
                key={session.id}
                className={`session-item${activeId === session.id ? " is-active" : ""}`}
              >
                <NavLink
                  to={`/chat/${session.id}`}
                  className="session-item-main"
                  title={session.title ?? `Conversa ${index + 1}`}
                >
                  <ChatIcon />
                  <span className="session-item-title">
                    {session.title?.trim() || `Conversa ${index + 1}`}
                  </span>
                </NavLink>
                <div className="session-actions">
                  <button
                    type="button"
                    className="session-menu-btn"
                    onClick={(event) => {
                      event.stopPropagation();
                      setOpenMenuId((current) => (current === session.id ? null : session.id));
                    }}
                    aria-label={`Mais ações para ${session.title?.trim() || `Conversa ${index + 1}`}`}
                    title="Mais ações"
                    aria-expanded={openMenuId === session.id}
                  >
                    <EllipsisIcon />
                  </button>
                  {openMenuId === session.id ? (
                    <div className="session-menu" role="menu">
                      <button
                        type="button"
                        className="session-menu-item"
                        onClick={async () => {
                          setOpenMenuId(null);
                          await onRename(session.id, session.title);
                        }}
                        role="menuitem"
                      >
                        Renomear
                      </button>
                      <button
                        type="button"
                        className="session-menu-item is-danger"
                        onClick={async () => {
                          setOpenMenuId(null);
                          await onDelete(session.id);
                        }}
                        role="menuitem"
                      >
                        <TrashIcon />
                        Remover conversa
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>
            ))
          )}
        </nav>

        <SidebarFooter showContext />
      </div>
    </aside>
  );
}
