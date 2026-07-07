/**
 * DocumentSummary — resumo de um documento no visualizador do painel (#44).
 * Busca o resumo existente; permite gerar/regerar via LLM. Reusa o molde do
 * document-viewer conforme planejado no épico de resumos.
 */

import { useEffect, useState } from "react";
import {
  generateMindmap,
  generateSingleSummary,
  getMindmap,
  getSingleSummary,
  type DocumentItem,
  type SummaryItem,
} from "../api/client";
import { MindmapView } from "./MindmapView";

export function DocumentSummary({ doc }: { doc: DocumentItem }) {
  const [summary, setSummary] = useState<SummaryItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [mindmap, setMindmap] = useState<SummaryItem | null>(null);
  const [mmGenerating, setMmGenerating] = useState(false);
  const [mmOpen, setMmOpen] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setMmOpen(false);
    getSingleSummary(doc.id)
      .then((s) => active && setSummary(s))
      .catch(() => active && setSummary(null))
      .finally(() => active && setLoading(false));
    getMindmap(doc.id)
      .then((m) => active && setMindmap(m))
      .catch(() => active && setMindmap(null));
    return () => {
      active = false;
    };
  }, [doc.id]);

  const genMindmap = async () => {
    setMmGenerating(true);
    setError(null);
    try {
      setMindmap(await generateMindmap(doc.id));
      setMmOpen(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao gerar o mapa mental");
    } finally {
      setMmGenerating(false);
    }
  };

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const s = await generateSingleSummary(doc.id);
      setSummary(s);
      setOpen(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao gerar o resumo");
    } finally {
      setGenerating(false);
    }
  };

  const ready = doc.extraction_status === "done";

  return (
    <div className="doc-summary">
      <div className="doc-summary-head">
        <span className="doc-summary-title">Resumo</span>
        {summary ? (
          <button className="doc-summary-toggle" onClick={() => setOpen((o) => !o)}>
            {open ? "Ocultar" : "Mostrar"}
          </button>
        ) : null}
        <button
          className="doc-summary-gen"
          onClick={() => void generate()}
          disabled={!ready || generating || loading}
          title={ready ? "Gerar resumo com IA" : "Extraia o texto do documento antes"}
        >
          {generating ? "Gerando…" : summary ? "Regerar" : "Gerar resumo"}
        </button>
      </div>
      {summary && open ? <div className="doc-summary-body md">{summary.content}</div> : null}

      <div className="doc-summary-head" style={{ marginTop: 12 }}>
        <span className="doc-summary-title">Mapa mental</span>
        {mindmap ? (
          <button className="doc-summary-toggle" onClick={() => setMmOpen((o) => !o)}>
            {mmOpen ? "Ocultar" : "Mostrar"}
          </button>
        ) : null}
        <button
          className="doc-summary-gen"
          onClick={() => void genMindmap()}
          disabled={!ready || mmGenerating || loading}
          title={ready ? "Gerar mapa mental com IA" : "Extraia o texto do documento antes"}
        >
          {mmGenerating ? "Gerando…" : mindmap ? "Regerar" : "Gerar mapa"}
        </button>
      </div>
      {mindmap && mmOpen ? <MindmapView markdown={mindmap.content} /> : null}

      {error ? <p className="doc-summary-error">{error}</p> : null}
      {!summary && !loading && !generating ? (
        <p className="doc-summary-empty">
          {ready ? "Ainda não há resumo. Gere um com IA." : "Extraia o texto para poder resumir."}
        </p>
      ) : null}
    </div>
  );
}
