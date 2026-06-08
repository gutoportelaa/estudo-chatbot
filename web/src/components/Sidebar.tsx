import React from "react";
import { useNavigate, useParams } from "react-router-dom";
import { SessionItem } from "../api/client";
import { Plus, MessageSquare } from "./icons_extra";

interface SidebarProps {
  sessions: SessionItem[];
  loading: boolean;
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ sessions, loading, isOpen, onClose }) => {
  const navigate = useNavigate();
  const { sessionId } = useParams<{ sessionId?: string }>();

  const handleNewChat = () => {
    navigate("/chat");
    if (window.innerWidth <= 768) {
      onClose();
    }
  };

  const handleSelectSession = (id: string) => {
    navigate(`/chat/${id}`);
    if (window.innerWidth <= 768) {
      onClose();
    }
  };

  return (
    <>
      {/* Overlay para mobile */}
      {isOpen && <div className="sidebar-overlay" onClick={onClose} />}
      
      <aside className={`sidebar ${isOpen ? "open" : ""}`}>
        <div className="sidebar-header">
          <button className="new-chat-btn" onClick={handleNewChat}>
            <Plus />
            <span>New Chat</span>
          </button>
        </div>

        <div className="sidebar-content">
          <div className="sidebar-section-title">Recent Chats</div>
          
          {loading ? (
            <div className="sidebar-loading">Loading...</div>
          ) : sessions.length === 0 ? (
            <div className="sidebar-empty">No chats yet.</div>
          ) : (
            <div className="session-list">
              {sessions.map((session) => (
                <button
                  key={session.id}
                  className={`session-item ${session.id === sessionId ? "active" : ""}`}
                  onClick={() => handleSelectSession(session.id)}
                >
                  <MessageSquare className="session-icon" />
                  <span className="session-title">
                    {session.title || "New Chat"}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </aside>
    </>
  );
};
