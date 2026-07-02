import { useEffect, useState } from "react";
import { fetchThumbnail, type DocumentItem } from "../api/client";
import { TrashIcon } from "./icons";

interface Props {
  doc: DocumentItem;
  selected: boolean;
  onToggle: () => void;
  onDelete: () => void;
}

function fmtSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

const STATUS_LABEL: Record<DocumentItem["extraction_status"], string> = {
  pending: "Processando…",
  done: "Pronto",
  failed: "Falhou",
};

export function DocumentCard({ doc, selected, onToggle, onDelete }: Props) {
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
    <div className={`doc-card${selected ? " is-selected" : ""}`}>
      <button
        type="button"
        className="doc-card-cover"
        onClick={onToggle}
        title={selected ? "Remover da seleção" : "Selecionar para conversa"}
      >
        {cover ? (
          <img src={cover} alt={`Capa de ${doc.filename}`} />
        ) : (
          <div className="doc-card-cover-fallback">
            <span>📄</span>
          </div>
        )}
        <span className="doc-card-check" aria-hidden>
          {selected ? "✓" : ""}
        </span>
      </button>

      <div className="doc-card-info">
        <span className="doc-card-name" title={doc.filename}>
          {doc.filename}
        </span>
        <span className="doc-card-meta">
          {fmtSize(doc.size_bytes)}
          {doc.page_count ? ` · ${doc.page_count} p.` : ""}
          {" · "}
          <span className={`doc-card-status is-${doc.extraction_status}`}>
            {STATUS_LABEL[doc.extraction_status]}
          </span>
        </span>
      </div>

      <button
        type="button"
        className="doc-card-delete"
        onClick={onDelete}
        aria-label={`Excluir ${doc.filename}`}
        title="Excluir"
      >
        <TrashIcon />
      </button>
    </div>
  );
}
