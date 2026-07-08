import { Navigate, useNavigate, useParams } from "react-router-dom";
import { SummaryDetailView } from "../components/SummaryDetailView";

export function SummaryDetailPage() {
  const { summaryId } = useParams<{ summaryId: string }>();
  const navigate = useNavigate();
  if (!summaryId) return <Navigate to="/resumos" replace />;
  return (
    <main className="content is-biblioteca">
      <SummaryDetailView summaryId={summaryId} onBack={() => navigate("/resumos")} />
    </main>
  );
}
