import { useLocation, useNavigate } from "react-router-dom";
import { ResumosView } from "../components/ResumosView";

interface LocationState {
  highlightId?: string;
}

export function ResumosPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state as LocationState | null) ?? null;

  return (
    <main className="content is-biblioteca">
      <ResumosView
        highlightId={state?.highlightId ?? null}
        onOpenSummary={(id) => navigate(`/resumos/${id}`)}
      />
    </main>
  );
}
