import { useEffect, useState } from "react";
import { getSummaries, type SummaryEvent } from "../api/client";
import { ContextInspector } from "./ContextInspector";

interface Props {
  sessionId: string | null;
  /** Muda a cada mensagem para revalidar após novas compactações. */
  refreshKey: number;
}

/**
 * Chip discreto que aparece quando o histórico da sessão já foi compactado
 * (sumarização, issue #31). O tooltip mostra a timeline das compactações —
 * "noção de desenvolvimento" de como a memória de longo prazo é montada.
 */
export function MemoryBadge({ sessionId, refreshKey }: Props) {
  const [events, setEvents] = useState<SummaryEvent[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!sessionId) {
      setEvents([]);
      return;
    }
    let active = true;
    getSummaries(sessionId)
      .then((e) => active && setEvents(e))
      .catch(() => active && setEvents([]));
    return () => {
      active = false;
    };
  }, [sessionId, refreshKey]);

  if (events.length === 0) return null;

  const tooltip = events
    .map((e, i) => {
      const kind = e.trigger === "recompaction" ? "resumo-de-resumo" : "janela cheia";
      return `${i + 1}. ${kind} · ${e.source_message_count} msgs → ${e.summary_tokens} tok`;
    })
    .join("\n");

  const label =
    events.length === 1 ? "1 compactação de memória" : `${events.length} compactações de memória`;

  return (
    <>
      <button
        type="button"
        className="memory-badge is-clickable"
        title={`${tooltip}\n\n(clique para ver a linha do tempo)`}
        onClick={() => setOpen(true)}
      >
        <span aria-hidden>🧠</span>
        <span>{label}</span>
      </button>
      {open && sessionId ? (
        <ContextInspector sessionId={sessionId} onClose={() => setOpen(false)} />
      ) : null}
    </>
  );
}
