import type { Theme } from "../hooks/useTheme";
import { LogoIcon, MoonIcon, SunIcon } from "./icons";

interface Props {
  theme: Theme;
  onToggleTheme: () => void;
}

export function Header({ theme, onToggleTheme }: Props) {
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
        <span className="avatar">M</span>
      </div>
    </header>
  );
}
