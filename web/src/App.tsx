import { useState } from "react";
import { Routes, Route, Navigate, useParams } from "react-router-dom";
import { ChatInput } from "./components/ChatInput";
import { Greeting } from "./components/Greeting";
import { Header } from "./components/Header";
import { MessageList } from "./components/MessageList";
import { PromptCards } from "./components/PromptCards";
import { Sidebar } from "./components/Sidebar";
import { Auth } from "./components/Auth";
import { useChat } from "./hooks/useChat";
import { useSessionsList } from "./hooks/useSessionsList";
import { useTheme } from "./hooks/useTheme";
import { useAuth } from "./hooks/useAuth";

function ChatLayout() {
  const [theme, toggleTheme] = useTheme();
  const { token } = useAuth();
  const { sessionId } = useParams<{ sessionId?: string }>();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [draft, setDraft] = useState("");
  
  const { sessions, loading: sessionsLoading, loadSessions } = useSessionsList();
  
  // Quando uma nova sessão for criada localmente (via envio de msg),
  // disparamos o recarregamento da lista de sessões para que a nova 
  // apareça na sidebar com o title gerado pelo backend.
  const { messages, isStreaming, send } = useChat(sessionId || null, loadSessions);

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  const hasConversation = messages.length > 0;

  return (
    <div className="app">
      <Sidebar 
        sessions={sessions} 
        loading={sessionsLoading} 
        isOpen={sidebarOpen} 
        onClose={() => setSidebarOpen(false)} 
      />
      
      <div className="window">
        <Header 
          theme={theme} 
          onToggleTheme={toggleTheme} 
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} 
        />

        <main className={`content ${hasConversation ? "is-chat" : "is-empty"}`}>
          {hasConversation ? (
            <MessageList messages={messages} />
          ) : (
            <div className="welcome">
              <Greeting />
              <PromptCards onPick={(p) => setDraft(p)} />
            </div>
          )}
        </main>

        <footer className="composer">
          <ChatInput
            value={draft}
            onChange={setDraft}
            onSend={send}
            disabled={isStreaming}
          />
          <div className="composer-footer">
            <span>ThinkAI can make mistakes. Please double-check responses.</span>
            <span className="hint">
              Use <kbd>shift + return</kbd> for new line
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
}

export default function App() {
  const { token } = useAuth();

  return (
    <Routes>
      <Route path="/" element={<Navigate to={token ? "/chat" : "/login"} replace />} />
      <Route path="/login" element={<Auth mode="login" />} />
      <Route path="/signup" element={<Auth mode="signup" />} />
      <Route path="/chat" element={<ChatLayout />} />
      <Route path="/chat/:sessionId" element={<ChatLayout />} />
    </Routes>
  );
}
