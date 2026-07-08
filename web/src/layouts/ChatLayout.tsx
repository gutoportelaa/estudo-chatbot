import { Outlet } from "react-router-dom";
import type { Theme } from "../hooks/useTheme";
import { useAppUI } from "../context/AppUIContext";
import { Header } from "../components/Header";
import { SidebarChat } from "../components/SidebarChat";

interface Props {
  theme: Theme;
  onToggleTheme: () => void;
  isAuthenticated: boolean;
  userLabel: string;
  onLogout: () => void;
}

export function ChatLayout({ theme, onToggleTheme, isAuthenticated, userLabel, onLogout }: Props) {
  const ui = useAppUI();
  return (
    <div className="app">
      <SidebarChat isAuthenticated={isAuthenticated} />
      <div className="window">
        <Header
          theme={theme}
          onToggleTheme={onToggleTheme}
          onToggleSidebar={ui.toggleSidebar}
          userLabel={userLabel}
          onLogout={onLogout}
        />
        <Outlet />
      </div>
    </div>
  );
}
