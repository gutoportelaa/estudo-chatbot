import type { Theme } from "../hooks/useTheme";
import { LogoIcon, MoonIcon, SunIcon } from "./icons";

interface Props {
  theme: Theme;
  onToggleTheme: () => void;
  username: string | null;
  onLogout: () => void;
}

export function Header({ theme, onToggleTheme, username, onLogout }: Props) {
  return (
    <header className="header">
      <div className="brand">
        <span className="brand-icon">
          <LogoIcon />
        </span>
        <span className="brand-name">ThinkAI</span>
      </div>

      <div className="header-right">
        <button
          className="icon-btn"
          onClick={onToggleTheme}
          aria-label="Alternar tema"
          title={theme === "light" ? "Tema escuro" : "Tema claro"}
        >
          {theme === "light" ? <MoonIcon /> : <SunIcon />}
        </button>
        <button
          className="avatar"
          onClick={onLogout}
          title="Sair"
          aria-label="Sair da conta"
        >
          {username ? username[0].toUpperCase() : "?"}
        </button>
      </div>
    </header>
  );
}
