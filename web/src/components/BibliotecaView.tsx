import { useCallback, useEffect, useRef, useState } from "react";
import {
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
}

const SORT_LABELS: Record<DocumentSort, string> = {
  recent: "Mais recentes",
  oldest: "Mais antigos",
  name: "Nome (A–Z)",
  size: "Tamanho",
};

export function BibliotecaView({ onStartConversation }: Props) {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [sort, setSort] = useState<DocumentSort>("recent");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
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

  // Fila de upload (concorrência 1): atualiza a grade ao concluir cada doc.
  const queue = useUploadQueue(async () => {
    await refresh();
  });
  const handleFiles = useCallback(
    (files: FileList | File[]) => queue.enqueue(Array.from(files)),
    [queue],
  );

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
  const selectedSize = selectedList.reduce((acc, d) => acc + d.size_bytes, 0);
  const bigSelection = selectedSize > 20 * 1024 * 1024; // ~aviso de seleção grande

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
          <p className="biblioteca-sub">Seus documentos. Selecione um ou mais para conversar.</p>
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
            {bigSelection ? " · seleção grande, a busca prioriza os trechos mais relevantes" : ""}
          </span>
          <div>
            <button className="btn-ghost" onClick={() => setSelected(new Set())}>
              Limpar
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
    </section>
  );
}
