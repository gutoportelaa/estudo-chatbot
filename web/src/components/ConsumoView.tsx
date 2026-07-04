/**
 * ConsumoView — página dedicada de observabilidade (como a Biblioteca).
 * ---------------------------------------------------------------------------
 * Dashboard de consumo por período: tokens, custo, latência, taxa de sucesso,
 * falhas, uso de ferramenta (RAG) e falhas recentes. Substitui o antigo modal.
 * Gráfico de tokens por dia em SVG (linhas com eixos) para leitura mais clara.
 */

import { useEffect, useMemo, useState } from "react";
import { getUsage, type UsageSummary } from "../api/client";

const RANGES = [
  { days: 7, label: "7 dias" },
  { days: 30, label: "30 dias" },
  { days: 90, label: "90 dias" },
];

function fmtInt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function fmtCost(n: number): string {
  if (n === 0) return "$0";
  if (n < 0.01) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(2)}`;
}

/** Gera o atributo `d` de uma polilinha normalizada num viewBox 0..W / 0..H. */
function linePath(values: number[], max: number, w: number, h: number, pad: number): string {
  if (values.length === 0) return "";
  const innerW = w - pad * 2;
  const innerH = h - pad * 2;
  const step = values.length > 1 ? innerW / (values.length - 1) : 0;
  return values
    .map((v, i) => {
      const x = pad + i * step;
      const y = pad + innerH - (max > 0 ? (v / max) * innerH : 0);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export function ConsumoView() {
  const [data, setData] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getUsage(days)
      .then(setData)
      .catch(() => setError("Não foi possível carregar o consumo."))
      .finally(() => setLoading(false));
  }, [days]);

  const totals = data?.totals;
  const byDay = data?.by_day ?? [];

  const chart = useMemo(() => {
    const W = 720;
    const H = 220;
    const pad = 32;
    const inputs = byDay.map((d) => d.input_tokens);
    const outputs = byDay.map((d) => d.output_tokens);
    const max = Math.max(1, ...inputs.map((v, i) => v + outputs[i]), ...inputs, ...outputs);
    return {
      W,
      H,
      pad,
      max,
      inputPath: linePath(inputs, max, W, H, pad),
      outputPath: linePath(outputs, max, W, H, pad),
    };
  }, [byDay]);

  const maxModel = Math.max(1, ...(data?.by_model ?? []).map((m) => m.input_tokens + m.output_tokens));
  const maxReq = Math.max(1, ...byDay.map((d) => d.requests));

  return (
    <section className="consumo">
      <header className="consumo-header">
        <div>
          <h2>Consumo</h2>
          <p className="consumo-sub">
            Tokens, custo, latência, falhas e ferramentas nos últimos {days} dias.
          </p>
        </div>
        <div className="usage-range" role="group" aria-label="Período">
          {RANGES.map((r) => (
            <button
              key={r.days}
              className={`usage-range-btn${days === r.days ? " is-active" : ""}`}
              onClick={() => setDays(r.days)}
            >
              {r.label}
            </button>
          ))}
        </div>
      </header>

      {loading ? <p className="usage-muted">Carregando…</p> : null}
      {error ? <p className="usage-muted">{error}</p> : null}

      {totals && !loading ? (
        <>
          <div className="usage-cards">
            <div className="usage-card">
              <span className="usage-card-value">{fmtInt(totals.requests)}</span>
              <span className="usage-card-label">Requisições</span>
            </div>
            <div className="usage-card">
              <span className="usage-card-value">
                {Math.round(totals.success_rate * 100)}%
              </span>
              <span className="usage-card-label">Taxa de sucesso</span>
            </div>
            <div className={`usage-card${totals.errors > 0 ? " is-alert" : ""}`}>
              <span className="usage-card-value">{fmtInt(totals.errors)}</span>
              <span className="usage-card-label">Falhas</span>
            </div>
            <div className="usage-card">
              <span className="usage-card-value">
                {fmtInt(totals.input_tokens + totals.output_tokens)}
              </span>
              <span className="usage-card-label">Tokens totais</span>
            </div>
            <div className="usage-card">
              <span className="usage-card-value">{fmtCost(totals.cost_usd)}</span>
              <span className="usage-card-label">Custo estimado</span>
            </div>
            <div className="usage-card">
              <span className="usage-card-value">{Math.round(totals.avg_latency_ms)} ms</span>
              <span className="usage-card-label">Latência média</span>
            </div>
            <div className="usage-card">
              <span className="usage-card-value">
                {totals.requests > 0
                  ? `${Math.round((totals.rag_requests / totals.requests) * 100)}%`
                  : "0%"}
              </span>
              <span className="usage-card-label">Usaram RAG</span>
            </div>
          </div>

          {byDay.length > 0 ? (
            <div className="consumo-panel">
              <div className="usage-section-head">
                <h3>Tokens por dia</h3>
                <div className="usage-legend">
                  <span className="usage-legend-item">
                    <i className="usage-swatch is-input" /> Entrada
                  </span>
                  <span className="usage-legend-item">
                    <i className="usage-swatch is-output" /> Saída
                  </span>
                </div>
              </div>
              <svg
                className="consumo-chart"
                viewBox={`0 0 ${chart.W} ${chart.H}`}
                preserveAspectRatio="none"
                role="img"
                aria-label="Gráfico de tokens por dia"
              >
                {[0, 0.25, 0.5, 0.75, 1].map((f) => {
                  const y = chart.pad + (chart.H - chart.pad * 2) * f;
                  return (
                    <g key={f}>
                      <line
                        className="consumo-grid"
                        x1={chart.pad}
                        y1={y}
                        x2={chart.W - chart.pad}
                        y2={y}
                      />
                      <text className="consumo-axis" x={4} y={y + 3}>
                        {fmtInt(Math.round(chart.max * (1 - f)))}
                      </text>
                    </g>
                  );
                })}
                <path className="consumo-line is-input" d={chart.inputPath} />
                <path className="consumo-line is-output" d={chart.outputPath} />
                <text className="consumo-axis" x={chart.pad} y={chart.H - 8}>
                  {byDay[0]?.date.slice(5)}
                </text>
                <text className="consumo-axis" x={chart.W - chart.pad} y={chart.H - 8} textAnchor="end">
                  {byDay[byDay.length - 1]?.date.slice(5)}
                </text>
              </svg>
            </div>
          ) : null}

          {byDay.length > 0 ? (
            <div className="consumo-panel">
              <div className="usage-section-head">
                <h3>Requisições e falhas por dia</h3>
                <div className="usage-legend">
                  <span className="usage-legend-item">
                    <i className="usage-swatch is-ok" /> Sucesso
                  </span>
                  <span className="usage-legend-item">
                    <i className="usage-swatch is-error" /> Falha
                  </span>
                </div>
              </div>
              <div className="usage-bars">
                {byDay.map((d) => {
                  const h = (d.requests / maxReq) * 100;
                  const errShare = d.requests > 0 ? (d.errors / d.requests) * 100 : 0;
                  return (
                    <div
                      key={d.date}
                      className="usage-bar-col"
                      title={`${d.date}: ${d.requests} req · ${d.errors} falha(s)`}
                    >
                      <div className="usage-bar usage-bar--stacked" style={{ height: `${h}%` }}>
                        <div className="usage-bar-seg is-error" style={{ height: `${errShare}%` }} />
                        <div className="usage-bar-seg is-ok" style={{ height: `${100 - errShare}%` }} />
                      </div>
                      <span className="usage-bar-label">{d.date.slice(5)}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}

          {data && data.by_model.length > 0 ? (
            <div className="consumo-panel">
              <h3>Por modelo</h3>
              <div className="usage-models">
                {data.by_model.map((m) => {
                  const total = m.input_tokens + m.output_tokens;
                  return (
                    <div key={m.model} className="usage-model-row">
                      <div className="usage-model-head">
                        <span className="usage-model-name">{m.model}</span>
                        <span className="usage-model-meta">
                          {fmtInt(m.requests)} reqs · {fmtInt(total)} tokens · {fmtCost(m.cost_usd)}
                        </span>
                      </div>
                      <div className="usage-model-bar">
                        <div
                          className="usage-model-fill"
                          style={{ width: `${(total / maxModel) * 100}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}

          {data && data.recent_errors.length > 0 ? (
            <div className="consumo-panel">
              <h3>Falhas recentes</h3>
              <ul className="consumo-errors">
                {data.recent_errors.map((e, i) => (
                  <li key={i} className="consumo-error-row">
                    <span className="consumo-error-meta">
                      {e.created_at.slice(0, 16).replace("T", " ")} · {e.model}
                    </span>
                    <span className="consumo-error-msg">{e.error}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {totals.requests === 0 ? (
            <p className="usage-muted">
              Ainda não há consumo registrado. Converse no chat para gerar métricas.
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
