import { useNavigate } from "react-router-dom";
import { BibliotecaView } from "../components/BibliotecaView";
import { useSessions } from "../hooks/useSessions";

interface Props {
  isAuthenticated: boolean;
}

export function BibliotecaPage({ isAuthenticated }: Props) {
  const navigate = useNavigate();
  const { createNewSession } = useSessions(isAuthenticated);

  return (
    <main className="content is-biblioteca">
      <BibliotecaView
        onStartConversation={async (documentIds) => {
          const id = await createNewSession(documentIds);
          navigate(`/chat/${id}`);
        }}
        onGenerateSummary={(summaryId) => {
          navigate("/resumos", { state: { highlightId: summaryId } });
        }}
      />
    </main>
  );
}
