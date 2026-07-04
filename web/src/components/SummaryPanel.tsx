/**
 * SummaryPanel — painel lateral direito (3ª coluna) exibindo o resumo gerado
 * a partir da seleção de documentos na Biblioteca. Reaproveita o mesmo
 * esqueleto visual do `DocumentPanel` (classes `doc-panel*`), que já previa
 * esse reuso para a geração de resumos.
 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { SummaryItem } from "../api/client";

interface Props {
  summary: SummaryItem | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}

export function SummaryPanel({ summary, loading, error, onClose }: Props) {
  return (
    <aside className="doc-panel" aria-label="Resumo de documentos">
      <header className="doc-panel-head">
        <h3 className="doc-panel-title">
          {summary?.kind === "consolidated" ? "Resumo consolidado" : "Resumo"}
        </h3>
        <button className="doc-panel-close" onClick={onClose} aria-label="Fechar painel">
          ×
        </button>
      </header>

      <div className="doc-panel-body">
        {loading ? (
          <p className="doc-panel-empty">Gerando resumo…</p>
        ) : error ? (
          <p className="doc-panel-notice">{error}</p>
        ) : summary ? (
          <div className="md">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{summary.content}</ReactMarkdown>
          </div>
        ) : (
          <p className="doc-panel-empty">Nenhum resumo selecionado.</p>
        )}
      </div>
    </aside>
  );
}
