/**
 * DocumentPanel — painel lateral direito (3ª coluna) do chat.
 * ---------------------------------------------------------------------------
 * Aberto pelo clipe do ChatInput. Empurra o chat (não é overlay) para manter
 * header/sidebar visíveis. Dois modos:
 *   - "list":   biblioteca compacta — anexar (com progresso/cancelamento),
 *               remover anexo e abrir a visualização de um documento.
 *   - "viewer": PDF completo embutido (referência: document-viewer do plebiscito).
 *
 * O mesmo esqueleto será reaproveitado pela futura geração de resumos (#5).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  attachDocuments,
  deleteDocument,
  detachDocument,
  extractDocument,
  fetchPdfUrl,
  fetchThumbnail,
  indexDocument,
  listDocuments,
  uploadDocumentWithProgress,
  type DocumentItem,
  type UploadHandle,
} from "../api/client";
import { PaperclipIcon, TrashIcon } from "./icons";

interface Props {
  sessionId: string | null;
  attachedIds: string[];
  onAttachedChange: (ids: string[]) => void;
  onClose: () => void;
}

interface Upload {
  name: string;
  percent: number;
  phase: "uploading" | "processing";
  handle: UploadHandle;
}

function fmtSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** Card de documento no painel — replica o visual da Biblioteca (capa + info),
 * com clique na capa abrindo o PDF e um botão de anexar/remover da conversa. */
function PanelDocCard({
  doc,
  attached,
  disabled,
  onView,
  onToggleAttach,
  onDelete,
}: {
  doc: DocumentItem;
  attached: boolean;
  disabled: boolean;
  onView: () => void;
  onToggleAttach: () => void;
  onDelete: () => void;
}) {
  const [cover, setCover] = useState<string | null>(null);

  useEffect(() => {
    if (!doc.has_thumbnail) return;
    let url: string | null = null;
    let active = true;
    fetchThumbnail(doc.id)
      .then((u) => {
        if (active) {
          url = u;
          setCover(u);
        } else {
          URL.revokeObjectURL(u);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [doc.id, doc.has_thumbnail]);

  return (
    <div className={`doc-card${attached ? " is-selected" : ""}`}>
      <button type="button" className="doc-card-cover" onClick={onView} title="Visualizar PDF">
        {cover ? (
          <img src={cover} alt={`Capa de ${doc.filename}`} />
        ) : (
          <div className="doc-card-cover-fallback">
            <span>📄</span>
          </div>
        )}
      </button>
      <button
        type="button"
        className="doc-card-delete"
        onClick={onDelete}
        aria-label={`Excluir ${doc.filename}`}
        title="Excluir da biblioteca"
      >
        <TrashIcon />
      </button>
      <div className="doc-card-info">
        <span className="doc-card-name" title={doc.filename}>
          {doc.filename}
        </span>
        <span className="doc-card-meta">{fmtSize(doc.size_bytes)}</span>
        <button
          type="button"
          className={`doc-card-attach${attached ? " is-on" : ""}`}
          onClick={onToggleAttach}
          disabled={disabled}
        >
          <PaperclipIcon /> {attached ? "Anexado" : "Anexar"}
        </button>
      </div>
    </div>
  );
}

export function DocumentPanel({ sessionId, attachedIds, onAttachedChange, onClose }: Props) {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [viewing, setViewing] = useState<DocumentItem | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [upload, setUpload] = useState<Upload | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      setDocs(await listDocuments("recent"));
    } catch {
      /* silencioso */
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Fecha o painel com Escape (ou volta da visualização para a lista).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (viewing) setViewing(null);
      else onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [viewing, onClose]);

  // Carrega o PDF autenticado como object URL ao abrir a visualização.
  useEffect(() => {
    if (!viewing) {
      setPdfUrl((url) => {
        if (url) URL.revokeObjectURL(url);
        return null;
      });
      return;
    }
    let revoked = false;
    let created: string | null = null;
    setPdfLoading(true);
    fetchPdfUrl(viewing.id)
      .then((url) => {
        if (revoked) {
          URL.revokeObjectURL(url);
          return;
        }
        created = url;
        setPdfUrl(url);
      })
      .catch(() => setNotice("Não foi possível abrir o PDF."))
      .finally(() => setPdfLoading(false));
    return () => {
      revoked = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [viewing]);

  const startUpload = useCallback(
    (file: File) => {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        setNotice("Apenas arquivos .pdf são aceitos.");
        return;
      }
      setNotice(null);
      const handle = uploadDocumentWithProgress(file, (percent) =>
        setUpload((u) => (u ? { ...u, percent } : u)),
      );
      setUpload({ name: file.name, percent: 0, phase: "uploading", handle });
      handle.promise
        .then(async (doc) => {
          setUpload((u) => (u ? { ...u, phase: "processing", percent: 100 } : u));
          await extractDocument(doc.id).catch(() => null);
          await indexDocument(doc.id).catch(() => null);
          await refresh();
          // Já anexa o recém-enviado à conversa ativa (fluxo do clipe).
          if (sessionId) {
            const ids = await attachDocuments(sessionId, [doc.id]).catch(() => null);
            if (ids) onAttachedChange(ids);
          }
          setNotice(`“${doc.filename}” adicionado.`);
        })
        .catch((err: unknown) => {
          const msg = err instanceof Error ? err.message : "Falha no upload";
          if (msg !== "Upload cancelado") setNotice(msg);
        })
        .finally(() => setUpload(null));
    },
    [refresh, sessionId, onAttachedChange],
  );

  const removeDoc = useCallback(
    async (doc: DocumentItem) => {
      if (!window.confirm(`Excluir “${doc.filename}” da biblioteca? Essa ação não pode ser desfeita.`))
        return;
      try {
        await deleteDocument(doc.id);
        if (sessionId && attachedIds.includes(doc.id)) {
          const ids = await detachDocument(sessionId, doc.id).catch(() => null);
          if (ids) onAttachedChange(ids);
        }
        await refresh();
      } catch {
        setNotice("Não foi possível excluir o documento.");
      }
    },
    [sessionId, attachedIds, onAttachedChange, refresh],
  );

  const toggleAttach = useCallback(
    async (doc: DocumentItem) => {
      if (!sessionId) return;
      try {
        const ids = attachedIds.includes(doc.id)
          ? await detachDocument(sessionId, doc.id)
          : await attachDocuments(sessionId, [doc.id]);
        onAttachedChange(ids);
      } catch {
        setNotice("Não foi possível atualizar o anexo.");
      }
    },
    [sessionId, attachedIds, onAttachedChange],
  );

  return (
    <aside className="doc-panel" aria-label="Documentos da conversa">
      <header className="doc-panel-head">
        {viewing ? (
          <button className="doc-panel-back" onClick={() => setViewing(null)} title="Voltar à lista">
            ← Voltar
          </button>
        ) : (
          <h3 className="doc-panel-title">
            <PaperclipIcon /> Documentos
          </h3>
        )}
        <button className="doc-panel-close" onClick={onClose} aria-label="Fechar painel">
          ×
        </button>
      </header>

      {viewing ? (
        <div className="doc-panel-viewer">
          <div className="doc-viewer-meta">
            <strong className="doc-viewer-name">{viewing.filename}</strong>
            <span className="doc-viewer-sub">
              {fmtSize(viewing.size_bytes)}
              {viewing.page_count ? ` · ${viewing.page_count} págs` : ""}
            </span>
          </div>
          {pdfLoading ? (
            <div className="doc-viewer-loading">Carregando PDF…</div>
          ) : pdfUrl ? (
            <iframe className="doc-viewer-frame" src={pdfUrl} title={viewing.filename} />
          ) : (
            <div className="doc-viewer-loading">Não foi possível exibir o PDF.</div>
          )}
        </div>
      ) : (
        <div className="doc-panel-body">
          <div className="doc-panel-actions">
            <button className="btn-primary" onClick={() => fileInput.current?.click()} disabled={!!upload}>
              + Adicionar PDF
            </button>
            <input
              ref={fileInput}
              type="file"
              accept="application/pdf"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) startUpload(f);
                e.target.value = "";
              }}
            />
          </div>

          {upload ? (
            <div className="upload-progress">
              <div className="upload-progress-row">
                <span className="upload-progress-name" title={upload.name}>
                  {upload.phase === "processing" ? "Processando" : "Enviando"} · {upload.name}
                </span>
                <button
                  className="upload-cancel"
                  onClick={() => upload.handle.cancel()}
                  disabled={upload.phase === "processing"}
                  title={upload.phase === "processing" ? "Não é possível cancelar o processamento" : "Cancelar"}
                >
                  Cancelar
                </button>
              </div>
              <div className="upload-bar">
                <div
                  className={`upload-bar-fill${upload.phase === "processing" ? " is-indeterminate" : ""}`}
                  style={{ width: `${upload.percent}%` }}
                />
              </div>
            </div>
          ) : null}

          {notice ? <p className="doc-panel-notice">{notice}</p> : null}

          {docs.length === 0 ? (
            <p className="doc-panel-empty">Nenhum documento ainda.</p>
          ) : (
            <div className="doc-grid doc-grid--panel">
              {docs.map((doc) => (
                <PanelDocCard
                  key={doc.id}
                  doc={doc}
                  attached={attachedIds.includes(doc.id)}
                  disabled={!sessionId}
                  onView={() => setViewing(doc)}
                  onToggleAttach={() => void toggleAttach(doc)}
                  onDelete={() => void removeDoc(doc)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </aside>
  );
}
