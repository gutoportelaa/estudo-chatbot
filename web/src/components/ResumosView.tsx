/**
 * ResumosView — lista de resumos em grid, com polling automático dos que ainda
 * estão processando. Card click abre o detalhamento.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { deleteSummary, listSummaries, type SummaryItem } from "../api/client";
import { useSummaryPolling } from "../hooks/useSummaryPolling";
import { TrashIcon } from "./icons";

interface Props {
  onOpenSummary: (id: string) => void;
  /** Id recém-criado (vindo da Biblioteca) para destacar/injetar sem esperar refresh. */
  highlightId?: string | null;
}

function statusInfo(s: SummaryItem["status"]): { label: string; className: string } {
  switch (s) {
    case "pending":
      return { label: "Na fila", className: "is-pending" };
    case "processing":
      return { label: "Processando…", className: "is-processing" };
    case "done":
      return { label: "Pronto", className: "is-done" };
    case "failed":
      return { label: "Falhou", className: "is-failed" };
  }
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const sec = Math.max(0, Math.round(diffMs / 1000));
  if (sec < 60) return `há ${sec}s`;
  const min = Math.round(sec / 60);
  if (min < 60) return `há ${min}min`;
  const h = Math.round(min / 60);
  if (h < 24) return `há ${h}h`;
  return new Date(iso).toLocaleDateString();
}

export function ResumosView({ onOpenSummary, highlightId }: Props) {
  const [items, setItems] = useState<SummaryItem[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setItems(await listSummaries());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const pendingIds = useMemo(
    () => items.filter((s) => s.status === "pending" || s.status === "processing").map((s) => s.id),
    [items],
  );

  // A cada tick, atualiza o mapa local; quando algum item terminou, refaz o
  // list para pegar content/mindmap completos (o poll só devolve status/title).
  useSummaryPolling(pendingIds, (statuses) => {
    let needsRefresh = false;
    setItems((cur) =>
      cur.map((it) => {
        const upd = statuses.find((s) => s.id === it.id);
        if (!upd) return it;
        if (upd.status !== it.status && (upd.status === "done" || upd.status === "failed")) {
          needsRefresh = true;
        }
        return { ...it, status: upd.status, error: upd.error, title: upd.title };
      }),
    );
    if (needsRefresh) void refresh();
  });

  const remove = async (id: string) => {
    if (!window.confirm("Excluir este resumo? Essa ação não pode ser desfeita.")) return;
    await deleteSummary(id);
    setItems((cur) => cur.filter((s) => s.id !== id));
  };

  return (
    <section className="resumos">
      <header className="resumos-head">
        <div>
          <h2>Resumos</h2>
          <p className="resumos-sub">
            Resumos gerados a partir da Biblioteca. Vá em Biblioteca, selecione documentos e clique em
            &ldquo;Gerar Resumo&rdquo;.
          </p>
        </div>
      </header>

      {loading ? (
        <p className="resumos-empty">Carregando…</p>
      ) : items.length === 0 ? (
        <p className="resumos-empty">Nenhum resumo ainda.</p>
      ) : (
        <div className="resumos-grid">
          {items.map((s) => {
            const info = statusInfo(s.status);
            const title = s.title?.trim() || (s.status === "done" ? "Sem título" : "Aguardando título…");
            const clickable = s.status === "done";
            const isHighlight = s.id === highlightId;
            return (
              <div
                key={s.id}
                className={`resumo-card ${info.className}${isHighlight ? " is-highlight" : ""}`}
              >
                <button
                  type="button"
                  className="resumo-card-body"
                  onClick={() => clickable && onOpenSummary(s.id)}
                  disabled={!clickable}
                  title={clickable ? "Abrir resumo" : info.label}
                >
                  <span className={`resumo-card-status ${info.className}`}>
                    {(s.status === "pending" || s.status === "processing") && (
                      <span className="resumo-card-spinner" aria-hidden />
                    )}
                    {info.label}
                  </span>
                  <h3 className="resumo-card-title">{title}</h3>
                  <p className="resumo-card-meta">
                    {s.document_ids.length} documento{s.document_ids.length > 1 ? "s" : ""} · {timeAgo(s.created_at)}
                  </p>
                  {s.status === "failed" && s.error ? (
                    <p className="resumo-card-error">{s.error}</p>
                  ) : null}
                </button>
                <button
                  type="button"
                  className="resumo-card-delete"
                  onClick={() => void remove(s.id)}
                  aria-label="Excluir resumo"
                  title="Excluir"
                >
                  <TrashIcon />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
