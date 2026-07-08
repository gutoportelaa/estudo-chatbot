/**
 * DashboardView — home pós-login (#46 E1).
 * Agrega o que já existe: acesso rápido, documentos recentes, resumos recentes e
 * um resumo de consumo. Fluxo navegável: upload → listar → resumir → ver.
 */

import { useEffect, useState } from "react";
import {
  getUsage,
  listDocuments,
  listSummaries,
  type DocumentItem,
  type SummaryItem,
  type UsageSummary,
} from "../api/client";
import { BookIcon, ChartIcon, PlusIcon, UserIcon } from "./icons";

interface Props {
  username: string;
  onNewChat: () => void;
  onOpenBiblioteca: () => void;
  onOpenResumos: () => void;
  onOpenConsumo: () => void;
  onOpenProfile: () => void;
}

const STATUS_LABEL: Record<SummaryItem["status"], string> = {
  pending: "Na fila",
  processing: "Processando",
  done: "Pronto",
  failed: "Falhou",
};

function fmtInt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

export function DashboardView({
  username,
  onNewChat,
  onOpenBiblioteca,
  onOpenResumos,
  onOpenConsumo,
  onOpenProfile,
}: Props) {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [summaries, setSummaries] = useState<SummaryItem[]>([]);
  const [usage, setUsage] = useState<UsageSummary | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      listDocuments("recent").catch(() => [] as DocumentItem[]),
      listSummaries().catch(() => [] as SummaryItem[]),
      getUsage(30).catch(() => null),
    ]).then(([d, s, u]) => {
      if (!active) return;
      setDocs(d.slice(0, 6));
      setSummaries(s.slice(0, 5));
      setUsage(u);
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="dashboard">
      <header className="dashboard-head">
        <h2>Olá, {username} 👋</h2>
        <p className="dashboard-sub">O que vamos estudar hoje?</p>
      </header>

      <div className="dashboard-actions">
        <button className="dash-action" onClick={onNewChat}>
          <PlusIcon />
          <span>Nova conversa</span>
        </button>
        <button className="dash-action" onClick={onOpenBiblioteca}>
          <BookIcon />
          <span>Biblioteca</span>
        </button>
        <button className="dash-action" onClick={onOpenConsumo}>
          <ChartIcon />
          <span>Consumo</span>
        </button>
        <button className="dash-action" onClick={onOpenProfile}>
          <UserIcon />
          <span>Perfil</span>
        </button>
      </div>

      {usage && usage.totals.requests > 0 ? (
        <div className="dashboard-usage">
          <div className="dash-metric">
            <strong>{fmtInt(usage.totals.requests)}</strong>
            <span>Requisições (30d)</span>
          </div>
          <div className="dash-metric">
            <strong>{fmtInt(usage.totals.input_tokens + usage.totals.output_tokens)}</strong>
            <span>Tokens</span>
          </div>
          <div className="dash-metric">
            <strong>{Math.round(usage.totals.success_rate * 100)}%</strong>
            <span>Sucesso</span>
          </div>
        </div>
      ) : null}

      <div className="dashboard-grid">
        <div className="dashboard-panel">
          <div className="dashboard-panel-head">
            <h3>Seus documentos</h3>
            <button className="btn-ghost" onClick={onOpenBiblioteca}>
              Ver todos
            </button>
          </div>
          {docs.length === 0 ? (
            <p className="dashboard-empty">
              Nenhum documento ainda. Abra a Biblioteca para enviar um PDF.
            </p>
          ) : (
            <ul className="dashboard-doclist">
              {docs.map((d) => (
                <li key={d.id} className="dashboard-docitem">
                  <span className="dashboard-doc-emoji" aria-hidden>
                    📄
                  </span>
                  <button className="dashboard-doc-name" onClick={onOpenBiblioteca} title={d.filename}>
                    {d.filename}
                  </button>
                  <span
                    className={`dashboard-doc-status is-${d.extraction_status}`}
                    title={`Extração: ${d.extraction_status}`}
                  >
                    {d.extraction_status === "done" ? "pronto" : d.extraction_status}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="dashboard-panel">
          <div className="dashboard-panel-head">
            <h3>Resumos recentes</h3>
            <button className="btn-ghost" onClick={onOpenResumos}>
              Ver todos
            </button>
          </div>
          {summaries.length === 0 ? (
            <p className="dashboard-empty">
              Nenhum resumo ainda. Selecione documentos na Biblioteca e clique em Gerar Resumo.
            </p>
          ) : (
            <ul className="dashboard-summlist">
              {summaries.map((s) => (
                <li key={s.id} className="dashboard-summitem">
                  <span className={`dashboard-summ-kind is-${s.status}`}>
                    {STATUS_LABEL[s.status]}
                  </span>
                  <span
                    className="dashboard-summ-preview"
                    title={s.title ?? s.content ?? ""}
                  >
                    {s.title?.trim() ||
                      (s.content ? s.content.slice(0, 120) + (s.content.length > 120 ? "…" : "") : "Aguardando…")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
