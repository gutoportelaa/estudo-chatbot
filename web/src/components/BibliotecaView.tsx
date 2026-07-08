import { useCallback, useEffect, useRef, useState } from "react";
import {
  createSummary,
  deleteDocument,
  listDocuments,
  type DocumentItem,
  type DocumentSort,
} from "../api/client";
import { useUploadQueue } from "../hooks/useUploadQueue";
import { DocumentCard } from "./DocumentCard";
import { UploadQueueList } from "./UploadQueueList";

interface Props {
  /** Inicia uma nova conversa restrita aos documentos selecionados. */
  onStartConversation: (documentIds: string[]) => void | Promise<void>;
  /** Dispara a geração de resumo dos documentos selecionados e navega para a aba Resumos. */
  onGenerateSummary: (summaryId: string) => void;
}

const SORT_LABELS: Record<DocumentSort, string> = {
  recent: "Mais recentes",
  oldest: "Mais antigos",
  name: "Nome (A–Z)",
  size: "Tamanho",
};

export function BibliotecaView({ onStartConversation, onGenerateSummary }: Props) {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [sort, setSort] = useState<DocumentSort>("recent");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setDocs(await listDocuments(sort));
    } finally {
      setLoading(false);
    }
  }, [sort]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const queue = useUploadQueue(async () => {
    await refresh();
  });
  const handleFiles = useCallback(
    (files: FileList | File[]) => queue.enqueue(Array.from(files)),
    [queue],
  );

  const generateSummary = useCallback(async () => {
    if (selected.size === 0) return;
    setGenerating(true);
    setSummaryError(null);
    try {
      const summary = await createSummary([...selected]);
      setSelected(new Set());
      onGenerateSummary(summary.id);
    } catch (e) {
      setSummaryError(e instanceof Error ? e.message : "Falha ao criar o resumo");
    } finally {
      setGenerating(false);
    }
  }, [selected, onGenerateSummary]);

  const toggle = (id: string) =>
    setSelected((cur) => {
      const next = new Set(cur);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const remove = async (id: string) => {
    if (!window.confirm("Excluir este documento? Essa ação não pode ser desfeita.")) return;
    await deleteDocument(id);
    setSelected((cur) => {
      const next = new Set(cur);
      next.delete(id);
      return next;
    });
    await refresh();
  };

  const selectedList = docs.filter((d) => selected.has(d.id));
  const notReady = selectedList.filter((d) => d.extraction_status !== "done");
  const canSummarize = selected.size > 0 && notReady.length === 0 && !generating;

  return (
    <section
      className={`biblioteca${dragOver ? " is-dragover" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        void handleFiles(e.dataTransfer.files);
      }}
    >
      <header className="biblioteca-header">
        <div>
          <h2>Biblioteca</h2>
          <p className="biblioteca-sub">Seus documentos. Selecione um ou mais para conversar ou resumir.</p>
        </div>
        <div className="biblioteca-actions">
          <select
            className="biblioteca-sort"
            value={sort}
            onChange={(e) => setSort(e.target.value as DocumentSort)}
            aria-label="Ordenar"
          >
            {(Object.keys(SORT_LABELS) as DocumentSort[]).map((s) => (
              <option key={s} value={s}>
                {SORT_LABELS[s]}
              </option>
            ))}
          </select>
          <button className="btn-primary" onClick={() => fileInput.current?.click()}>
            + Adicionar
          </button>
          <input
            ref={fileInput}
            type="file"
            accept="application/pdf"
            multiple
            hidden
            onChange={(e) => {
              if (e.target.files) void handleFiles(e.target.files);
              e.target.value = "";
            }}
          />
        </div>
      </header>

      <UploadQueueList queue={queue} />

      {docs.length === 0 && !loading ? (
        <div className="biblioteca-dropzone">
          <p>Arraste PDFs aqui ou clique em “+ Adicionar”.</p>
        </div>
      ) : (
        <div className="doc-grid">
          {docs.map((doc) => (
            <DocumentCard
              key={doc.id}
              doc={doc}
              selected={selected.has(doc.id)}
              onToggle={() => toggle(doc.id)}
              onDelete={() => void remove(doc.id)}
            />
          ))}
        </div>
      )}

      {selected.size > 0 ? (
        <div className="biblioteca-selbar">
          <span>
            {selected.size} selecionado{selected.size > 1 ? "s" : ""}
            {notReady.length > 0
              ? ` · ${notReady.length} sem texto extraído (aguarde)`
              : ""}
          </span>
          <div>
            <button className="btn-ghost" onClick={() => setSelected(new Set())}>
              Limpar
            </button>
            <button
              className="btn-ghost"
              onClick={() => void generateSummary()}
              disabled={!canSummarize}
              title={
                notReady.length > 0
                  ? "Aguarde a extração dos documentos selecionados"
                  : "Gera resumo + mapa mental (assíncrono)"
              }
            >
              {generating ? "Enviando…" : "Gerar Resumo"}
            </button>
            <button
              className="btn-primary"
              onClick={() => void onStartConversation([...selected])}
            >
              Nova conversa com {selected.size} documento{selected.size > 1 ? "s" : ""}
            </button>
          </div>
        </div>
      ) : null}

      {summaryError ? <p className="biblioteca-busy">{summaryError}</p> : null}
    </section>
  );
}
