/**
 * DocumentPanel — painel lateral informativo (3ª coluna) do chat.
 * ---------------------------------------------------------------------------
 * Só exibe: as fontes (trechos de RAG) usadas para responder a mensagem clicada.
 * Cada card = 1 chunk recuperado, com documento, página e trecho. Upload e
 * geração de resumos ficam na Biblioteca; anexação de docs a uma conversa
 * acontece ao criar a conversa lá.
 */

import { useMemo } from "react";
import { fetchPdfUrl, type MessageSource } from "../api/client";
import { PaperclipIcon } from "./icons";

interface Props {
  sources: MessageSource[];
  onClose: () => void;
}

function openPdfInTab(documentId: string, page?: number | null): void {
  // Baixa autenticado como blob e abre em nova aba (o <a href> não envia JWT).
  void fetchPdfUrl(documentId).then((url) => {
    const anchor = page ? `${url}#page=${page}` : url;
    window.open(anchor, "_blank", "noopener");
    // Deixa o browser controlar o revoke do object URL (fica preso à aba nova).
  });
}

export function DocumentPanel({ sources, onClose }: Props) {
  const cards = useMemo(() => sources.filter((s) => s.kind === "rag"), [sources]);

  return (
    <aside className="doc-panel" aria-label="Fontes desta resposta">
      <header className="doc-panel-head">
        <h3 className="doc-panel-title">
          <PaperclipIcon /> Fontes desta resposta
        </h3>
        <button className="doc-panel-close" onClick={onClose} aria-label="Fechar painel">
          ×
        </button>
      </header>

      <div className="doc-panel-body">
        {cards.length === 0 ? (
          <p className="doc-panel-empty">Sem trechos de material para esta mensagem.</p>
        ) : (
          <ol className="source-cards">
            {cards.map((s, i) => (
              <li key={`${s.document_id}-${s.chunk_index}-${i}`} className="source-card">
                <div className="source-card-head">
                  <span className="source-card-idx">{i + 1}</span>
                  <span className="source-card-name" title={s.title}>
                    📄 {s.title}
                  </span>
                </div>
                <div className="source-card-meta">
                  {s.page != null ? `Página ${s.page}` : `Trecho ${(s.chunk_index ?? 0) + 1}`}
                </div>
                {s.snippet ? (
                  <blockquote className="source-card-snippet">{s.snippet}</blockquote>
                ) : null}
                {s.document_id ? (
                  <div className="source-card-actions">
                    <button
                      type="button"
                      className="btn-ghost"
                      onClick={() => openPdfInTab(s.document_id!, s.page)}
                    >
                      Abrir PDF{s.page != null ? ` na página ${s.page}` : ""}
                    </button>
                  </div>
                ) : null}
              </li>
            ))}
          </ol>
        )}
      </div>
    </aside>
  );
}
