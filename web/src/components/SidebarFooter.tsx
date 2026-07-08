import { NavLink } from "react-router-dom";
import { useAppUI } from "../context/AppUIContext";
import { ChartIcon, ChatIcon, SettingsIcon, UserIcon } from "./icons";

interface Props {
  /** Mostra o item de Contexto (só faz sentido dentro do chat). */
  showContext?: boolean;
}

export function SidebarFooter({ showContext = false }: Props) {
  const ui = useAppUI();
  return (
    <div className="sidebar-footer">
      <NavLink
        to="/consumo"
        className={({ isActive }) =>
          `sidebar-prefs-btn${isActive ? " is-active" : ""}`
        }
        title="Consumo de tokens e custo"
      >
        <ChartIcon />
        <span>Consumo</span>
      </NavLink>
      {showContext ? (
        <button
          className="sidebar-prefs-btn"
          onClick={ui.openContext}
          title="Memória e janela de contexto"
        >
          <ChatIcon />
          <span>Contexto</span>
        </button>
      ) : null}
      <button
        className="sidebar-prefs-btn"
        onClick={ui.openProfile}
        title="Perfil do usuário"
      >
        <UserIcon />
        <span>Perfil</span>
      </button>
      <button
        className="sidebar-prefs-btn"
        onClick={ui.openPreferences}
        title="Preferências"
      >
        <SettingsIcon />
        <span>Preferências</span>
      </button>
    </div>
  );
}
