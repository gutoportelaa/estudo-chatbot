import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { listSummaries, type SummaryItem } from "../api/client";

/** Lista todos os resumos (individual/consolidado) do usuário, expansíveis. */
export function SummaryListView() {
  const [summaries, setSummaries] = useState<SummaryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setSummaries(await listSummaries());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <section className="biblioteca">
      <header className="biblioteca-header">
        <div>
          <h2>Resumos</h2>
          <p className="biblioteca-sub">Resumos individuais e consolidados já gerados.</p>
        </div>
      </header>

      {loading ? (
        <p className="biblioteca-busy">Carregando…</p>
      ) : summaries.length === 0 ? (
        <div className="biblioteca-dropzone">
          <p>Nenhum resumo gerado ainda. Vá em Biblioteca, selecione documentos e gere um resumo.</p>
        </div>
      ) : (
        <div className="summary-list">
          {summaries.map((s) => (
            <div key={s.id} className="summary-list-item">
              <button
                type="button"
                className="summary-list-header"
                onClick={() => setExpandedId((cur) => (cur === s.id ? null : s.id))}
              >
                <span>{s.kind === "consolidated" ? "Resumo consolidado" : "Resumo"}</span>
                <span className="doc-card-meta">
                  {s.document_ids.length} documento{s.document_ids.length > 1 ? "s" : ""} ·{" "}
                  {new Date(s.created_at).toLocaleString()}
                </span>
              </button>
              {expandedId === s.id ? (
                <div className="md summary-list-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{s.content}</ReactMarkdown>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
