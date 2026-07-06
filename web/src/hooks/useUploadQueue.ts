/**
 * useUploadQueue — fila de upload de PDFs com progresso, cancelamento e retry.
 * ---------------------------------------------------------------------------
 * Concorrência 1 (não martelar o rate limit do embedder em produção). Cada item
 * percorre: enfileirado → enviando (cancelável via abort) → processando
 * (extract → index) → concluído | falhou (retry) | cancelado.
 *
 * O cancelamento durante o *envio* aborta o XHR (nada persiste — o PUT é atômico).
 * Durante o *processamento* não há worker para abortar no servidor: marcamos como
 * cancelado e paramos de aguardar; o documento pode já existir e ser excluído
 * manualmente. Retry re-enfileira (reusa o arquivo; se já subiu, só reprocessa).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  extractDocument,
  indexDocument,
  uploadDocumentWithProgress,
  type DocumentItem,
  type UploadHandle,
} from "../api/client";

export type UploadStatus =
  | "queued"
  | "uploading"
  | "processing"
  | "done"
  | "failed"
  | "canceled";

export interface UploadItem {
  id: string;
  name: string;
  size: number;
  status: UploadStatus;
  percent: number;
  docId?: string;
  error?: string;
}

interface Internal extends UploadItem {
  file: File;
  handle?: UploadHandle;
}

function uid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function useUploadQueue(onDocumentReady: (doc: DocumentItem) => void | Promise<void>) {
  const [items, setItems] = useState<UploadItem[]>([]);
  const itemsRef = useRef<Internal[]>([]);
  const runningRef = useRef(false);
  const readyRef = useRef(onDocumentReady);
  readyRef.current = onDocumentReady;

  const sync = useCallback(() => {
    // Projeta o estado interno (sem File/handle) para o consumidor.
    setItems(itemsRef.current.map(({ file: _f, handle: _h, ...pub }) => pub));
  }, []);

  const patch = useCallback(
    (id: string, partial: Partial<Internal>) => {
      itemsRef.current = itemsRef.current.map((it) =>
        it.id === id ? { ...it, ...partial } : it,
      );
      sync();
    },
    [sync],
  );

  const isCanceled = (id: string) =>
    itemsRef.current.find((it) => it.id === id)?.status === "canceled";

  const runItem = useCallback(async (id: string) => {
    const item = itemsRef.current.find((it) => it.id === id);
    if (!item || item.status === "canceled") return;

    // Fase de envio (pulada no retry pós-upload, quando já há docId).
    let docId = item.docId;
    if (!docId) {
      const handle = uploadDocumentWithProgress(item.file, (percent) => patch(id, { percent }));
      patch(id, { status: "uploading", percent: 0, error: undefined, handle });
      try {
        const doc = await handle.promise;
        docId = doc.id;
        patch(id, { docId, name: doc.filename });
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Falha no upload";
        patch(id, { status: msg === "Upload cancelado" ? "canceled" : "failed", error: msg, handle: undefined });
        return;
      }
    }
    if (isCanceled(id)) return;

    // Fase de processamento (extração + indexação para RAG).
    patch(id, { status: "processing", percent: 100, handle: undefined });
    try {
      await extractDocument(docId);
      if (isCanceled(id)) return;
      await indexDocument(docId);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Falha no processamento";
      patch(id, { status: "failed", error: msg });
      return;
    }
    if (isCanceled(id)) return;

    patch(id, { status: "done" });
    const doc = { id: docId, filename: item.name } as DocumentItem;
    await readyRef.current(doc);
    // Auto-remove itens concluídos após um instante (mantém a lista limpa).
    setTimeout(() => {
      itemsRef.current = itemsRef.current.filter((it) => !(it.id === id && it.status === "done"));
      sync();
    }, 2000);
  }, [patch, sync]);

  const pump = useCallback(async () => {
    if (runningRef.current) return;
    runningRef.current = true;
    try {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const next = itemsRef.current.find((it) => it.status === "queued");
        if (!next) break;
        await runItem(next.id);
      }
    } finally {
      runningRef.current = false;
    }
  }, [runItem]);

  const enqueue = useCallback(
    (files: File[]) => {
      const pdfs = files.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
      if (pdfs.length === 0) return;
      const added: Internal[] = pdfs.map((file) => ({
        id: uid(),
        name: file.name,
        size: file.size,
        status: "queued",
        percent: 0,
        file,
      }));
      itemsRef.current = [...itemsRef.current, ...added];
      sync();
      void pump();
    },
    [pump, sync],
  );

  const cancel = useCallback(
    (id: string) => {
      const item = itemsRef.current.find((it) => it.id === id);
      if (!item) return;
      if (item.status === "uploading" && item.handle) item.handle.cancel();
      patch(id, { status: "canceled", handle: undefined });
    },
    [patch],
  );

  const retry = useCallback(
    (id: string) => {
      // Re-enfileira: se já subiu (docId), só reprocessa; senão, reenvia.
      patch(id, { status: "queued", error: undefined, percent: 0 });
      void pump();
    },
    [patch, pump],
  );

  const dismiss = useCallback(
    (id: string) => {
      itemsRef.current = itemsRef.current.filter((it) => it.id !== id);
      sync();
    },
    [sync],
  );

  // Ao desmontar, aborta uploads em voo.
  useEffect(() => {
    return () => {
      itemsRef.current.forEach((it) => it.handle?.cancel());
    };
  }, []);

  return { items, enqueue, cancel, retry, dismiss };
}
