import { NavLink, useNavigate } from "react-router-dom";
import { useAppUI } from "../context/AppUIContext";
import { useSessions } from "../hooks/useSessions";
import { BookIcon, HomeIcon, PlusIcon, QuoteIcon } from "./icons";
import { SidebarFooter } from "./SidebarFooter";

interface Props {
  isAuthenticated: boolean;
}

export function SidebarMain({ isAuthenticated }: Props) {
  const ui = useAppUI();
  const navigate = useNavigate();
  const { createNewSession } = useSessions(isAuthenticated);

  const onNewChat = async () => {
    try {
      const id = await createNewSession();
      navigate(`/chat/${id}`);
    } catch {
      /* erro silencioso — usuário pode retry */
    }
  };

  return (
    <aside
      className={`sidebar${ui.sidebarOpen ? "" : " is-collapsed"}`}
      aria-label="Navegação principal"
    >
      <div className="sidebar-inner">
        <button
          className="sidebar-new-btn"
          onClick={() => void onNewChat()}
          title="Nova conversa"
        >
          <PlusIcon />
          <span>Nova conversa</span>
        </button>

        <NavLink
          to="/inicio"
          className={({ isActive }) =>
            `sidebar-nav-btn${isActive ? " is-active" : ""}`
          }
          title="Início"
        >
          <HomeIcon />
          <span>Início</span>
        </NavLink>

        <NavLink
          to="/biblioteca"
          className={({ isActive }) =>
            `sidebar-nav-btn${isActive ? " is-active" : ""}`
          }
          title="Biblioteca de documentos"
        >
          <BookIcon />
          <span>Biblioteca</span>
        </NavLink>

        <NavLink
          to="/resumos"
          className={({ isActive }) =>
            `sidebar-nav-btn${isActive ? " is-active" : ""}`
          }
          title="Resumos gerados"
        >
          <QuoteIcon />
          <span>Resumos</span>
        </NavLink>

        <div className="sidebar-spacer" />

        <SidebarFooter />
      </div>
    </aside>
  );
}
