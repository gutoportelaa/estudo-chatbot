import { type FormEvent, useEffect, useRef, useState } from "react";
import { fetchModelName, getSessionDocuments } from "./api/client";
import { ChatInput } from "./components/ChatInput";
import { DocumentPanel } from "./components/DocumentPanel";
import { Greeting } from "./components/Greeting";
import { Header } from "./components/Header";
import { MessageList } from "./components/MessageList";
import { PromptCards } from "./components/PromptCards";
import { Sidebar } from "./components/Sidebar";
import { useAuth } from "./hooks/useAuth";
import { useChat } from "./hooks/useChat";
import { useSessions } from "./hooks/useSessions";
import { useTheme } from "./hooks/useTheme";
import { PreferencesModal } from "./components/PreferencesModal";
import { ConsumoView } from "./components/ConsumoView";
import { MemoryBadge } from "./components/MemoryBadge";
import { BibliotecaView } from "./components/BibliotecaView";

export default function App() {
  const { theme, toggleTheme, colorStart, colorEnd, setColorStart, setColorEnd } = useTheme();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [prefsOpen, setPrefsOpen] = useState(false);
  const [view, setView] = useState<"chat" | "biblioteca" | "consumo">("chat");
  const [modelName, setModelName] = useState("");

  useEffect(() => {
    void fetchModelName().then(setModelName);
  }, []);
  const auth = useAuth();
  const sessions = useSessions(auth.user?.id ?? null, auth.isAuthenticated);
  const sessionId = sessions.activeSessionId;
  const { messages, isStreaming, send } = useChat(sessionId);
  const [draft, setDraft] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [authMode, setAuthMode] = useState<"signin" | "signup">("signin");

  // Documentos escopados à conversa atual (Biblioteca / clipe do chat).
  const [attachedIds, setAttachedIds] = useState<string[]>([]);
  const [panelOpen, setPanelOpen] = useState(false);

  useEffect(() => {
    if (!sessionId) {
      setAttachedIds([]);
      return;
    }
    let active = true;
    getSessionDocuments(sessionId)
      .then((ids) => active && setAttachedIds(ids))
      .catch(() => active && setAttachedIds([]));
    return () => {
      active = false;
    };
  }, [sessionId]);

  // Título é gerado no backend no 1º turno; ao encerrar o streaming, se a sessão
  // ainda estiver sem título (ex.: conversa iniciada pela Biblioteca), sincroniza
  // a lista para o título aparecer no sidebar.
  const prevStreaming = useRef(false);
  useEffect(() => {
    const finished = prevStreaming.current && !isStreaming;
    prevStreaming.current = isStreaming;
    if (!finished) return;
    const current = sessions.sessions.find((s) => s.id === sessionId);
    if (current && !current.title?.trim()) void sessions.refresh();
  }, [isStreaming, sessionId, sessions]);

  const hasConversation = messages.length > 0;

  if (auth.isLoading) {
    return (
      <div className="app">
        <div className="window">
          <Header theme={theme} onToggleTheme={toggleTheme} />
          <main className="content is-empty">
            <div className="welcome">
              <div className="orb" />
              <h1 className="greeting-title">Carregando...</h1>
            </div>
          </main>
        </div>
      </div>
    );
  }

  if (!auth.isAuthenticated || !auth.user) {
    const submitAuth = async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!username.trim() || !password.trim()) return;
      try {
        if (authMode === "signin") {
          await auth.login(username.trim(), password);
        } else {
          await auth.register(username.trim(), password);
        }
        setPassword("");
      } catch {
        // error shown via auth.error
      }
    };

    return (
      <div className="app">
        <div className="window">
          <Header theme={theme} onToggleTheme={toggleTheme} />
          <main className="content is-empty">
            <div className="welcome">
              <div className="orb" />
              <h1 className="greeting-title">Entre para continuar</h1>
              <p className="greeting-subtitle">
                Chatbot multiusuário com sessões separadas por conta.
              </p>

              <form className="auth-card" onSubmit={submitAuth}>
                <div className="auth-mode">
                  <button
                    type="button"
                    className={authMode === "signin" ? "auth-tab is-active" : "auth-tab"}
                    onClick={() => setAuthMode("signin")}
                  >
                    Entrar
                  </button>
                  <button
                    type="button"
                    className={authMode === "signup" ? "auth-tab is-active" : "auth-tab"}
                    onClick={() => setAuthMode("signup")}
                  >
                    Criar conta
                  </button>
                </div>

                <label className="auth-field">
                  <span>Usuário</span>
                  <input
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    autoComplete="username"
                    placeholder="Digite seu usuário"
                  />
                </label>

                <label className="auth-field">
                  <span>Senha</span>
                  <input
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    type="password"
                    autoComplete={authMode === "signin" ? "current-password" : "new-password"}
                    placeholder="••••••••"
                  />
                </label>

                {auth.error ? <p className="auth-error">{auth.error}</p> : null}

                <button className="auth-submit" type="submit" disabled={auth.isLoading}>
                  {auth.isLoading ? "Aguarde..." : authMode === "signin" ? "Entrar" : "Criar e entrar"}
                </button>
              </form>
            </div>
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <Sidebar
        sessions={sessions.sessions}
        activeSessionId={sessionId}
        isOpen={sidebarOpen}
        onSelect={(id) => {
          setView("chat");
          sessions.setActiveSessionId(id);
        }}
        onNew={() => {
          setView("chat");
          void sessions.createNewSession();
        }}
        onRename={async (id, currentTitle) => {
          const currentLabel = currentTitle?.trim() || "Conversa sem título";
          const nextTitle = window.prompt("Novo nome da conversa", currentLabel);
          if (nextTitle === null) return;
          const trimmed = nextTitle.trim();
          if (!trimmed) return;
          await sessions.updateSessionTitle(id, trimmed);
        }}
        onDelete={async (id) => {
          const sessionTitle = sessions.sessions.find((session) => session.id === id)?.title?.trim();
          const label = sessionTitle || "esta conversa";
          if (!window.confirm(`Apagar ${label}? Essa ação não pode ser desfeita.`)) return;
          await sessions.removeSession(id);
        }}
        onOpenPreferences={() => setPrefsOpen(true)}
        onOpenUsage={() => setView("consumo")}
        onOpenBiblioteca={() => setView("biblioteca")}
        bibliotecaActive={view === "biblioteca"}
        consumoActive={view === "consumo"}
      />

      <PreferencesModal
        isOpen={prefsOpen}
        onClose={() => setPrefsOpen(false)}
        colorStart={colorStart}
        colorEnd={colorEnd}
        setColorStart={setColorStart}
        setColorEnd={setColorEnd}
      />

      <div className="window">
        <Header
          theme={theme}
          onToggleTheme={toggleTheme}
          onToggleSidebar={() => setSidebarOpen((o) => !o)}
          userLabel={auth.user.username}
          onLogout={auth.logout}
        />

        <div className={`window-body${panelOpen && view === "chat" ? " has-panel" : ""}`}>
          <div className="chat-column">
            {view === "consumo" ? (
              <main className="content is-biblioteca">
                <ConsumoView />
              </main>
            ) : view === "biblioteca" ? (
              <main className="content is-biblioteca">
                <BibliotecaView
                  onStartConversation={async (documentIds) => {
                    await sessions.createNewSession(documentIds);
                    setView("chat");
                  }}
                />
              </main>
            ) : (
              <main className={`content ${hasConversation ? "is-chat" : "is-empty"}`}>
                {hasConversation ? (
                  <>
                    <MemoryBadge sessionId={sessionId} refreshKey={messages.length} />
                    <MessageList messages={messages} />
                  </>
                ) : (
                  <div className="welcome">
                    <Greeting username={auth.user.username} />
                    <PromptCards onPick={(p) => setDraft(p)} />
                  </div>
                )}
              </main>
            )}

            {view === "chat" ? (
              <footer className="composer">
                <ChatInput
                  value={draft}
                  onChange={setDraft}
                  onSend={(text) => {
                    setDraft("");
                    send(text);
                  }}
                  disabled={isStreaming || !sessionId}
                  modelName={modelName}
                  onOpenAttach={() => setPanelOpen((o) => !o)}
                  attachedCount={attachedIds.length}
                />
                <div className="composer-footer">
                  <span>O ThinkAI pode cometer erros. Verifique as respostas.</span>
                  <span className="hint">
                    Use <kbd>shift + return</kbd> para nova linha
                  </span>
                </div>
              </footer>
            ) : null}
          </div>

          {panelOpen && view === "chat" ? (
            <DocumentPanel
              sessionId={sessionId}
              attachedIds={attachedIds}
              onAttachedChange={setAttachedIds}
              onClose={() => setPanelOpen(false)}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
