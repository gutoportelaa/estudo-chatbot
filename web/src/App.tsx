import { type FormEvent, useState } from "react";
import { ChatInput } from "./components/ChatInput";
import { Greeting } from "./components/Greeting";
import { Header } from "./components/Header";
import { MessageList } from "./components/MessageList";
import { PromptCards } from "./components/PromptCards";
import { useChat } from "./hooks/useChat";
import { useAuth } from "./hooks/useAuth";
import { useSessions } from "./hooks/useSessions";
import { useTheme } from "./hooks/useTheme";

export default function App() {
  const [theme, toggleTheme] = useTheme();
  const auth = useAuth();
  const sessions = useSessions(auth.user?.id ?? null, auth.isAuthenticated);
  const sessionId = sessions.activeSessionId;
  const { messages, isStreaming, send } = useChat(sessionId);
  const [draft, setDraft] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [authMode, setAuthMode] = useState<"signin" | "signup">("signin");

  const hasConversation = messages.length > 0;

  const submitAuth = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!username.trim() || !password.trim()) return;

    if (authMode === "signin") {
      await auth.login(username.trim(), password);
    } else {
      await auth.register(username.trim(), password);
    }

    setPassword("");
  };

  if (auth.isLoading) {
    return (
      <div className="app">
        <div className="window">
          <Header theme={theme} onToggleTheme={toggleTheme} />
          <main className="content is-empty">
            <div className="welcome">
              <div className="orb" />
              <h1 className="greeting-title">Carregando sua sessão...</h1>
              <p className="greeting-subtitle">Validando autenticação e recuperando dados.</p>
            </div>
          </main>
        </div>
      </div>
    );
  }

  if (!auth.isAuthenticated || !auth.user) {
    return (
      <div className="app">
        <div className="window">
          <Header theme={theme} onToggleTheme={toggleTheme} />

          <main className="content is-empty">
            <div className="welcome">
              <div className="orb" />
              <h1 className="greeting-title">Entre para continuar</h1>
              <p className="greeting-subtitle">
                Protótipo funcional de chatbot multiusuário com sessões separadas por conta.
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

                <button className="send-btn auth-submit" type="submit" disabled={auth.isLoading}>
                  {authMode === "signin" ? "Entrar" : "Criar e entrar"}
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
      <div className="window">
        <Header
          theme={theme}
          onToggleTheme={toggleTheme}
          userLabel={auth.user.username}
          onLogout={auth.logout}
        />

        <div className="sessions-bar">
          <label className="sessions-select">
            <span>Sessão</span>
            <select
              value={sessionId ?? ""}
              onChange={(event) => sessions.setActiveSessionId(event.target.value)}
              disabled={!sessions.sessions.length}
            >
              {sessions.sessions.map((session, index) => (
                <option key={session.id} value={session.id}>
                  {session.title?.trim() || `Sessão ${index + 1}`}
                </option>
              ))}
            </select>
          </label>

          <button className="refresh-prompts" onClick={() => void sessions.createNewSession()}>
            Nova sessão
          </button>
        </div>

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
            disabled={isStreaming || !sessionId}
          />
          <div className="composer-footer">
            <span>O ThinkAI pode cometer erros. Verifique as respostas.</span>
            <span className="hint">
              Use <kbd>shift + return</kbd> para nova linha
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
}
