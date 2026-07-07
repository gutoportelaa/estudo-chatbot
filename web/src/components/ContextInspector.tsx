/**
 * ContextInspector — visual da gestão recursiva da janela de contexto (#31/D).
 * ---------------------------------------------------------------------------
 * Mostra a timeline das compactações do histórico (sumarização): cada evento
 * indica se foi por "janela cheia" (window_overflow) ou "resumo-de-resumo"
 * (recompaction) — deixando visível a recursão da memória de longo prazo.
 */

import { useEffect, useState } from "react";
import {
  getSessionContext,
  getSummaries,
  type ContextState,
  type SummaryEvent,
} from "../api/client";

const BLOCK_LABEL: Record<string, string> = {
  system: "Sistema",
  summary: "Resumo",
  rag: "RAG",
  recent: "Recentes",
  tool: "Ferramenta",
};

interface Props {
  sessionId: string;
  onClose: () => void;
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function ContextInspector({ sessionId, onClose }: Props) {
  const [events, setEvents] = useState<SummaryEvent[]>([]);
  const [ctx, setCtx] = useState<ContextState | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([
      getSummaries(sessionId).catch(() => [] as SummaryEvent[]),
      getSessionContext(sessionId).catch(() => null),
    ])
      .then(([e, c]) => {
        if (!active) return;
        setEvents(e);
        setCtx(c);
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [sessionId]);

  const totalCompacted = events.reduce((acc, e) => acc + e.source_message_count, 0);
  const recompactions = events.filter((e) => e.trigger === "recompaction").length;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Memória do contexto</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Fechar" title="Fechar">
            ✕
          </button>
        </div>
        <div className="modal-body">
          <p className="prefs-desc">
            Como o histórico longo é compactado para caber na janela do modelo: cada
            passo condensa mensagens antigas num resumo; quando o próprio resumo cresce
            demais, ele é recompactado (resumo-de-resumo).
          </p>

          {!loading && ctx ? (
            <div className="ctx-budget">
              <div className="usage-section-head">
                <h3>Janela do último turno</h3>
                <span className="ctx-budget-total">
                  {ctx.input_tokens} tokens de entrada · {ctx.model}
                </span>
              </div>
              <div className="ctx-budget-bar">
                {(["system", "summary", "rag", "recent", "tool"] as const).map((k) => {
                  const v = ctx.breakdown[k];
                  if (!v) return null;
                  const pct = ctx.input_tokens > 0 ? (v / ctx.input_tokens) * 100 : 0;
                  return (
                    <div
                      key={k}
                      className={`ctx-budget-seg is-${k}`}
                      style={{ width: `${pct}%` }}
                      title={`${BLOCK_LABEL[k]}: ${v} tokens`}
                    />
                  );
                })}
              </div>
              <div className="ctx-budget-legend">
                {(["system", "summary", "rag", "recent", "tool"] as const).map((k) =>
                  ctx.breakdown[k] ? (
                    <span key={k} className="ctx-budget-legend-item">
                      <i className={`ctx-budget-swatch is-${k}`} /> {BLOCK_LABEL[k]} · {ctx.breakdown[k]}
                    </span>
                  ) : null,
                )}
              </div>
            </div>
          ) : null}

          {loading ? (
            <p className="usage-muted">Carregando…</p>
          ) : events.length === 0 ? (
            <p className="usage-muted">
              Ainda não houve compactação nesta conversa — o histórico cabe inteiro na
              janela.
            </p>
          ) : (
            <>
              <div className="ctx-stats">
                <div className="ctx-stat">
                  <span className="ctx-stat-value">{events.length}</span>
                  <span className="ctx-stat-label">Compactações</span>
                </div>
                <div className="ctx-stat">
                  <span className="ctx-stat-value">{totalCompacted}</span>
                  <span className="ctx-stat-label">Mensagens resumidas</span>
                </div>
                <div className="ctx-stat">
                  <span className="ctx-stat-value">{recompactions}</span>
                  <span className="ctx-stat-label">Resumos-de-resumo</span>
                </div>
              </div>

              <ol className="ctx-timeline">
                {events.map((e, i) => {
                  const recompact = e.trigger === "recompaction";
                  return (
                    <li key={e.id} className={`ctx-step${recompact ? " is-recompact" : ""}`}>
                      <span className="ctx-step-dot" aria-hidden />
                      <div className="ctx-step-body">
                        <div className="ctx-step-head">
                          <span className="ctx-step-order">#{i + 1}</span>
                          <span className={`ctx-step-kind${recompact ? " is-recompact" : ""}`}>
                            {recompact ? "resumo-de-resumo" : "janela cheia"}
                          </span>
                          <span className="ctx-step-date">{fmtDate(e.created_at)}</span>
                        </div>
                        <div className="ctx-step-meta">
                          condensou <strong>{e.source_message_count}</strong> msgs · cobre{" "}
                          <strong>{e.covered_message_count}</strong> no total · resumo com{" "}
                          <strong>{e.summary_tokens}</strong> tokens
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ol>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
