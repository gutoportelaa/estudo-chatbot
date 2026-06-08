import type { SessionSummary } from "../api/client";
import { ChatIcon, PlusIcon } from "./icons";

interface Props {
  sessions: SessionSummary[];
  activeSessionId: string | null;
  isOpen: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
}

export function Sidebar({ sessions, activeSessionId, isOpen, onSelect, onNew }: Props) {
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
              <button
                key={session.id}
                className={`session-item${activeSessionId === session.id ? " is-active" : ""}`}
                onClick={() => onSelect(session.id)}
                title={session.title ?? `Conversa ${index + 1}`}
              >
                <ChatIcon />
                <span className="session-item-title">
                  {session.title?.trim() || `Conversa ${index + 1}`}
                </span>
              </button>
            ))
          )}
        </nav>
      </div>
    </aside>
  );
}
