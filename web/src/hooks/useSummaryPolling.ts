/**
 * useSummaryPolling — bate em `POST /summaries/status` de 3 em 3 segundos com os
 * ids que ainda estão em `pending`/`processing`. Para quando a lista fica vazia
 * (todos os resumos viraram `done`/`failed`). O consumidor recebe o mapa
 * `{id → status}` em cada tick e decide o que atualizar.
 */

import { useEffect, useRef } from "react";
import { pollSummaries, type SummaryStatusPoll } from "../api/client";

const INTERVAL_MS = 3000;

export function useSummaryPolling(
  pendingIds: string[],
  onTick: (statuses: SummaryStatusPoll[]) => void,
) {
  const cbRef = useRef(onTick);
  cbRef.current = onTick;

  useEffect(() => {
    if (pendingIds.length === 0) return;
    let alive = true;
    const tick = async () => {
      try {
        const rows = await pollSummaries(pendingIds);
        if (alive) cbRef.current(rows);
      } catch {
        /* falha transiente: espera o próximo tick */
      }
    };
    // primeiro tick imediato (feedback rápido pro usuário), depois interval.
    void tick();
    const id = window.setInterval(tick, INTERVAL_MS);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [pendingIds.join(",")]);
}
