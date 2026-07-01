import { useEffect, useState } from "react";
import { getUsage, type UsageSummary } from "../api/client";

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

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

export function ConsumptionModal({ isOpen, onClose }: Props) {
  const [data, setData] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    setError(null);
    getUsage(30)
      .then(setData)
      .catch(() => setError("Não foi possível carregar o consumo."))
      .finally(() => setLoading(false));
  }, [isOpen]);

  if (!isOpen) return null;

  const totals = data?.totals;
  const maxDay = Math.max(1, ...(data?.by_day ?? []).map((d) => d.input_tokens + d.output_tokens));

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content modal-content--wide" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Consumo</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Fechar" title="Fechar">
            ✕
          </button>
        </div>
        <div className="modal-body">
          <p className="prefs-desc">Uso de tokens, custo e latência nos últimos 30 dias.</p>

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
                  <span className="usage-card-value">{fmtInt(totals.input_tokens)}</span>
                  <span className="usage-card-label">Tokens de entrada</span>
                </div>
                <div className="usage-card">
                  <span className="usage-card-value">{fmtInt(totals.output_tokens)}</span>
                  <span className="usage-card-label">Tokens de saída</span>
                </div>
                <div className="usage-card">
                  <span className="usage-card-value">{fmtCost(totals.cost_usd)}</span>
                  <span className="usage-card-label">Custo estimado</span>
                </div>
                <div className="usage-card">
                  <span className="usage-card-value">{Math.round(totals.avg_latency_ms)} ms</span>
                  <span className="usage-card-label">Latência média</span>
                </div>
              </div>

              {data && data.by_day.length > 0 ? (
                <div className="usage-section">
                  <h3>Tokens por dia</h3>
                  <div className="usage-bars">
                    {data.by_day.map((d) => {
                      const total = d.input_tokens + d.output_tokens;
                      return (
                        <div key={d.date} className="usage-bar-col" title={`${d.date}: ${fmtInt(total)} tokens · ${fmtCost(d.cost_usd)}`}>
                          <div className="usage-bar" style={{ height: `${(total / maxDay) * 100}%` }} />
                          <span className="usage-bar-label">{d.date.slice(5)}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              {data && data.by_model.length > 0 ? (
                <div className="usage-section">
                  <h3>Por modelo</h3>
                  <table className="usage-table">
                    <thead>
                      <tr>
                        <th>Modelo</th>
                        <th>Reqs</th>
                        <th>Entrada</th>
                        <th>Saída</th>
                        <th>Custo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.by_model.map((m) => (
                        <tr key={m.model}>
                          <td>{m.model}</td>
                          <td>{fmtInt(m.requests)}</td>
                          <td>{fmtInt(m.input_tokens)}</td>
                          <td>{fmtInt(m.output_tokens)}</td>
                          <td>{fmtCost(m.cost_usd)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}

              {totals.requests === 0 ? (
                <p className="usage-muted">Ainda não há consumo registrado. Converse no chat para gerar métricas.</p>
              ) : null}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
