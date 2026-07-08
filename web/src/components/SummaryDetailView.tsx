/**
 * SummaryDetailView — detalhamento de um resumo, com tabs [Resumo | Mapa mental].
 * Referência simplificada do lecture-viewer do IAsmim.
 */

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getSummary, type SummaryDetail } from "../api/client";
import { MindmapView } from "./MindmapView";

interface Props {
  summaryId: string;
  onBack: () => void;
}

export function SummaryDetailView({ summaryId, onBack }: Props) {
  const [summary, setSummary] = useState<SummaryDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"resumo" | "mindmap">("resumo");

  useEffect(() => {
    let active = true;
    setLoading(true);
    getSummary(summaryId)
      .then((s) => active && setSummary(s))
      .catch(() => active && setSummary(null))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [summaryId]);

  if (loading) {
    return (
      <section className="summary-detail">
        <div className="summary-detail-loading">Carregando…</div>
      </section>
    );
  }
  if (!summary) {
    return (
      <section className="summary-detail">
        <div className="summary-detail-empty">
          <p>Resumo não encontrado.</p>
          <button className="btn-ghost" onClick={onBack}>
            ← Voltar
          </button>
        </div>
      </section>
    );
  }

  const created = new Date(summary.created_at).toLocaleString();

  return (
    <section className="summary-detail">
      <header className="summary-detail-head">
        <button className="btn-ghost summary-detail-back" onClick={onBack}>
          ← Voltar
        </button>
        <div className="summary-detail-title">
          <h2>{summary.title?.trim() || "Resumo sem título"}</h2>
          <span className="summary-detail-meta">
            {created}
            {summary.llm_model ? ` · ${summary.llm_model}` : ""}
          </span>
        </div>
      </header>

      {summary.documents.length > 0 ? (
        <div className="summary-detail-docs">
          <span className="summary-detail-docs-label">Fontes:</span>
          {summary.documents.map((d) => (
            <span key={d.id} className="summary-detail-chip" title={d.filename}>
              📄 {d.filename}
            </span>
          ))}
        </div>
      ) : null}

      <div className="summary-detail-tabs" role="tablist">
        <button
          role="tab"
          aria-selected={tab === "resumo"}
          className={`summary-detail-tab${tab === "resumo" ? " is-active" : ""}`}
          onClick={() => setTab("resumo")}
        >
          Resumo
        </button>
        <button
          role="tab"
          aria-selected={tab === "mindmap"}
          className={`summary-detail-tab${tab === "mindmap" ? " is-active" : ""}`}
          onClick={() => setTab("mindmap")}
        >
          Mapa mental
        </button>
      </div>

      <div className="summary-detail-body">
        {tab === "resumo" ? (
          summary.content ? (
            <div className="md">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{summary.content}</ReactMarkdown>
            </div>
          ) : (
            <p className="summary-detail-empty-tab">Sem conteúdo.</p>
          )
        ) : summary.mindmap ? (
          <MindmapView markdown={summary.mindmap} />
        ) : (
          <p className="summary-detail-empty-tab">Sem mapa mental.</p>
        )}
      </div>
    </section>
  );
}
