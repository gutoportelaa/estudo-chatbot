import { type FormEvent, useState } from "react";
import { Header } from "./Header";
import type { Theme } from "../hooks/useTheme";

interface Props {
  theme: Theme;
  onToggleTheme: () => void;
  isLoading: boolean;
  error: string | null;
  onSignIn: (username: string, password: string) => Promise<unknown>;
  onSignUp: (username: string, password: string) => Promise<unknown>;
}

export function AuthPage({ theme, onToggleTheme, isLoading, error, onSignIn, onSignUp }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"signin" | "signup">("signin");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!username.trim() || !password.trim()) return;
    try {
      if (mode === "signin") await onSignIn(username.trim(), password);
      else await onSignUp(username.trim(), password);
      setPassword("");
    } catch {
      /* erro renderizado via prop */
    }
  };

  return (
    <div className="app">
      <div className="window">
        <Header theme={theme} onToggleTheme={onToggleTheme} />
        <main className="content is-empty">
          <div className="welcome">
            <div className="orb" />
            <h1 className="greeting-title">Entre para continuar</h1>
            <p className="greeting-subtitle">
              Chatbot multiusuário com sessões separadas por conta.
            </p>

            <form className="auth-card" onSubmit={submit}>
              <div className="auth-mode">
                <button
                  type="button"
                  className={mode === "signin" ? "auth-tab is-active" : "auth-tab"}
                  onClick={() => setMode("signin")}
                >
                  Entrar
                </button>
                <button
                  type="button"
                  className={mode === "signup" ? "auth-tab is-active" : "auth-tab"}
                  onClick={() => setMode("signup")}
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
                  autoComplete={mode === "signin" ? "current-password" : "new-password"}
                  placeholder="••••••••"
                />
              </label>

              {error ? <p className="auth-error">{error}</p> : null}

              <button className="auth-submit" type="submit" disabled={isLoading}>
                {isLoading ? "Aguarde..." : mode === "signin" ? "Entrar" : "Criar e entrar"}
              </button>
            </form>
          </div>
        </main>
      </div>
    </div>
  );
}
