import type { Theme } from "../hooks/useTheme";
import { LogoIcon, MenuIcon, MoonIcon, SunIcon } from "./icons";

interface Props {
  theme: Theme;
  onToggleTheme: () => void;
  onToggleSidebar?: () => void;
  userLabel?: string | null;
  onLogout?: () => void;
}

export function Header({ theme, onToggleTheme, onToggleSidebar, userLabel, onLogout }: Props) {
  const avatarLabel = userLabel?.trim().charAt(0).toUpperCase() ?? "?";

  return (
    <header className="header">
      <div className="header-left">
        {onToggleSidebar ? (
          <button className="icon-btn" onClick={onToggleSidebar} aria-label="Alternar sidebar" title="Menu">
            <MenuIcon />
          </button>
        ) : null}
        <div className="brand">
          <span className="brand-icon">
            <LogoIcon />
          </span>
          <span className="brand-name">ThinkAI</span>
        </div>
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
          <button className="avatar" onClick={onLogout} title="Sair" aria-label="Sair da conta">
            {avatarLabel}
          </button>
        ) : null}
      </div>
    </header>
  );
}
