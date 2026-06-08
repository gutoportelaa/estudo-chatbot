import type { Theme } from "../hooks/useTheme";
import { LogoIcon, MoonIcon, SunIcon } from "./icons";

interface Props {
  theme: Theme;
  onToggleTheme: () => void;
  userLabel?: string | null;
  onLogout?: () => void;
}

export function Header({ theme, onToggleTheme, userLabel, onLogout }: Props) {
  const avatarLabel = userLabel?.trim().charAt(0).toUpperCase() ?? "M";

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
        {onLogout ? (
          <button className="icon-btn" onClick={onLogout} aria-label="Sair" title="Sair">
            ⎋
          </button>
        ) : null}
        <span className="avatar">{avatarLabel}</span>
      </div>
    </header>
  );
}
