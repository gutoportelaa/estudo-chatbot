import { useNavigate } from "react-router-dom";
import { DashboardView } from "../components/DashboardView";
import { useAppUI } from "../context/AppUIContext";
import { useSessions } from "../hooks/useSessions";

interface Props {
  username: string;
  isAuthenticated: boolean;
}

export function DashboardPage({ username, isAuthenticated }: Props) {
  const navigate = useNavigate();
  const ui = useAppUI();
  const { createNewSession } = useSessions(isAuthenticated);

  return (
    <main className="content is-biblioteca">
      <DashboardView
        username={username}
        onNewChat={async () => {
          try {
            const id = await createNewSession();
            navigate(`/chat/${id}`);
          } catch {
            /* silencioso */
          }
        }}
        onOpenBiblioteca={() => navigate("/biblioteca")}
        onOpenResumos={() => navigate("/resumos")}
        onOpenConsumo={() => navigate("/consumo")}
        onOpenProfile={ui.openProfile}
      />
    </main>
  );
}
