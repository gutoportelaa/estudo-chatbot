import type { SessionSummary } from "../api/client";
import { ChartIcon, ChatIcon, EllipsisIcon, PlusIcon, TrashIcon, SettingsIcon } from "./icons";
import { useState } from "react";

interface Props {
  sessions: SessionSummary[];
  activeSessionId: string | null;
  isOpen: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, currentTitle: string | null | undefined) => void | Promise<void>;
  onDelete: (id: string) => void;
  onOpenPreferences: () => void;
  onOpenUsage: () => void;
}

export function Sidebar({
  sessions,
  activeSessionId,
  isOpen,
  onSelect,
  onNew,
  onRename,
  onDelete,
  onOpenPreferences,
  onOpenUsage,
}: Props) {
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  return (
    <aside className={`sidebar${isOpen ? "" : " is-collapsed"}`} aria-label="Sessões">
      <div className="sidebar-inner">
        <button className="sidebar-new-btn" onClick={onNew} title="Nova conversa">
          <PlusIcon />
          <span>Nova conversa</span>
        </button>

        <nav className="sidebar-sessions">
          {sessions.length === 0 ? (
            <p className="sidebar-empty">Nenhuma sessão ainda</p>
          ) : (
            sessions.map((session, index) => (
              <div
                key={session.id}
                className={`session-item${activeSessionId === session.id ? " is-active" : ""}`}
              >
                <button
                  type="button"
                  className="session-item-main"
                  onClick={() => onSelect(session.id)}
                  title={session.title ?? `Conversa ${index + 1}`}
                >
                  <ChatIcon />
                  <span className="session-item-title">
                    {session.title?.trim() || `Conversa ${index + 1}`}
                  </span>
                </button>
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

        <div className="sidebar-footer">
          <button className="sidebar-prefs-btn" onClick={onOpenUsage} title="Consumo de tokens e custo">
            <ChartIcon />
            <span>Consumo</span>
          </button>
          <button className="sidebar-prefs-btn" onClick={onOpenPreferences} title="Preferências">
            <SettingsIcon />
            <span>Preferências</span>
          </button>
        </div>
      </div>
    </aside>
  );
}
