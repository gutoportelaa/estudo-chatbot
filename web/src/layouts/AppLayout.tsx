import { Outlet } from "react-router-dom";
import type { Theme } from "../hooks/useTheme";
import { useAppUI } from "../context/AppUIContext";
import { Header } from "../components/Header";
import { SidebarMain } from "../components/SidebarMain";

interface Props {
  theme: Theme;
  onToggleTheme: () => void;
  isAuthenticated: boolean;
  userLabel: string;
  onLogout: () => void;
}

export function AppLayout({ theme, onToggleTheme, isAuthenticated, userLabel, onLogout }: Props) {
  const ui = useAppUI();
  return (
    <div className="app">
      <SidebarMain isAuthenticated={isAuthenticated} />
      <div className="window">
        <Header
          theme={theme}
          onToggleTheme={onToggleTheme}
          onToggleSidebar={ui.toggleSidebar}
          userLabel={userLabel}
          onLogout={onLogout}
        />
        <div className="window-body">
          <div className="chat-column">
            <Outlet />
          </div>
        </div>
      </div>
    </div>
  );
}
