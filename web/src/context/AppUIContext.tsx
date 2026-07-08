/**
 * AppUIContext — estado de UI global (modais e toggle da sidebar).
 * Reduz prop drilling entre layouts, sidebars e páginas.
 */

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

interface AppUIState {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  preferencesOpen: boolean;
  openPreferences: () => void;
  closePreferences: () => void;
  profileOpen: boolean;
  openProfile: () => void;
  closeProfile: () => void;
  contextOpen: boolean;
  openContext: () => void;
  closeContext: () => void;
}

const AppUIContext = createContext<AppUIState | null>(null);

export function AppUIProvider({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [preferencesOpen, setPreferencesOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);

  const value = useMemo<AppUIState>(
    () => ({
      sidebarOpen,
      toggleSidebar: () => setSidebarOpen((o) => !o),
      preferencesOpen,
      openPreferences: () => setPreferencesOpen(true),
      closePreferences: () => setPreferencesOpen(false),
      profileOpen,
      openProfile: () => setProfileOpen(true),
      closeProfile: () => setProfileOpen(false),
      contextOpen,
      openContext: () => setContextOpen(true),
      closeContext: () => setContextOpen(false),
    }),
    [sidebarOpen, preferencesOpen, profileOpen, contextOpen],
  );

  return <AppUIContext.Provider value={value}>{children}</AppUIContext.Provider>;
}

export function useAppUI(): AppUIState {
  const ctx = useContext(AppUIContext);
  if (!ctx) throw new Error("useAppUI deve ser usado dentro de <AppUIProvider>");
  return ctx;
}
