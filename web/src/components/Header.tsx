import type { Theme } from "../hooks/useTheme";
import { useAuth } from "../hooks/useAuth";
import { LogoIcon, MoonIcon, SunIcon } from "./icons";
import { MenuIcon, LogOutIcon } from "./icons_extra";

interface Props {
  theme: Theme;
  onToggleTheme: () => void;
  onToggleSidebar: () => void;
}

export function Header({ theme, onToggleTheme, onToggleSidebar }: Props) {
  const { logout } = useAuth();

  return (
    <header className="header">
      <div className="brand">
        <button className="icon-btn sidebar-toggle" onClick={onToggleSidebar} aria-label="Menu">
          <MenuIcon />
        </button>
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
          className="icon-btn"
          onClick={logout}
          aria-label="Sair"
          title="Sair da conta"
        >
          <LogOutIcon />
        </button>
      </div>
    </header>
  );
}
