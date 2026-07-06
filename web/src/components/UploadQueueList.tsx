/**
 * UploadQueueList — render compartilhado da fila de upload (#13).
 * Usado no DocumentPanel (clipe) e na Biblioteca.
 */

import type { useUploadQueue, UploadItem, UploadStatus } from "../hooks/useUploadQueue";

const STATUS_LABEL: Record<UploadStatus, string> = {
  queued: "Na fila",
  uploading: "Enviando",
  processing: "Processando",
  done: "Concluído",
  failed: "Falhou",
  canceled: "Cancelado",
};

type Queue = ReturnType<typeof useUploadQueue>;

/** Ação contextual de um item: cancelar, retry ou dispensar. */
function UploadItemAction({ item, queue }: { item: UploadItem; queue: Queue }) {
  if (item.status === "queued" || item.status === "uploading") {
    return (
      <button className="upload-cancel" onClick={() => queue.cancel(item.id)}>
        Cancelar
      </button>
    );
  }
  if (item.status === "failed") {
    return (
      <button className="upload-cancel" onClick={() => queue.retry(item.id)}>
        Tentar de novo
      </button>
    );
  }
  if (item.status === "processing") {
    return <span className="upload-item-hint">…</span>;
  }
  return (
    <button className="upload-cancel" onClick={() => queue.dismiss(item.id)} aria-label="Remover da lista">
      ×
    </button>
  );
}

export function UploadQueueList({ queue }: { queue: Queue }) {
  if (queue.items.length === 0) return null;
  return (
    <ul className="upload-queue">
      {queue.items.map((it) => (
        <li key={it.id} className={`upload-item is-${it.status}`}>
          <div className="upload-item-row">
            <span className="upload-item-name" title={it.name}>
              {it.name}
            </span>
            <UploadItemAction item={it} queue={queue} />
          </div>
          <div className="upload-item-foot">
            <span className="upload-item-status">{STATUS_LABEL[it.status]}</span>
            <div className="upload-bar">
              <div
                className={`upload-bar-fill${it.status === "processing" ? " is-indeterminate" : ""}`}
                style={{ width: `${it.status === "queued" ? 0 : it.percent}%` }}
              />
            </div>
          </div>
          {it.error && it.status === "failed" ? (
            <span className="upload-item-error" title={it.error}>
              {it.error}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
