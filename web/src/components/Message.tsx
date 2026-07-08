import { useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "../hooks/useChat";
import type { MessageSource } from "../api/client";
import { MindmapView } from "./MindmapView";
import { QuoteIcon } from "./icons";

// Renderiza blocos ```markmap como mapa mental interativo (#36); demais códigos
// seguem o comportamento padrão.
const markdownComponents: Components = {
  code({ className, children, ...props }) {
    if (/\blanguage-markmap\b/.test(className ?? "")) {
      return <MindmapView markdown={String(children).trim()} />;
    }
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
};

function stageLabel(stage: string): string {
  const [name, count] = stage.split(":");
  switch (name) {
    case "searching":
      return "Buscando na web…";
    case "reading":
      return `Lendo ${count ?? ""} fonte${count === "1" ? "" : "s"}…`;
    case "generating":
      return "Sintetizando a resposta…";
    case "search_empty":
      return "Nada encontrado na web";
    default:
      return "Processando…";
  }
}

export function Message({
  message,
  onOpenSource,
  onOpenSources,
}: {
  message: ChatMessage;
  onOpenSource?: (source: MessageSource) => void;
  onOpenSources?: (sources: MessageSource[]) => void;
}) {
  const isUser = message.role === "user";

  const stageNode =
    message.streaming && message.stage ? (
      <div className="msg-stage">
        <span className="msg-stage-spinner" aria-hidden />
        {stageLabel(message.stage)}
      </div>
    ) : null;

  let body: React.ReactNode;
  if (!message.content) {
    body = stageNode ?? <span className="typing-dots"><i /><i /><i /></span>;
  } else if (isUser) {
    body = message.content;
  } else if (message.streaming) {
    // Durante o stream: texto plano para evitar markdown parcial quebrado
    body = <span className="streaming-text">{message.content}</span>;
  } else {
    body = (
      <div className="md">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
          {message.content}
        </ReactMarkdown>
      </div>
    );
  }

  const sources = !isUser && !message.streaming ? message.sources : null;
  const hasSources = !!sources && sources.length > 0;

  return (
    <div className={`message ${isUser ? "message-user" : "message-assistant"}`}>
      {!isUser && (
        <span className="message-avatar" aria-hidden>
          <span className="orb orb-sm" />
        </span>
      )}
      <div className="message-bubble">{body}</div>
      {hasSources ? (
        <ReferenceToggle
          sources={sources}
          onOpenSource={onOpenSource}
          onOpenAll={() => onOpenSources?.(sources)}
        />
      ) : null}
    </div>
  );
}

/** Ícone lateral discreto que abre um popover com as referências da mensagem.
 * Um botão extra "Ver fontes" abre o painel lateral com todos os trechos em
 * cards (fluxo do DocumentPanel informativo). */
function ReferenceToggle({
  sources,
  onOpenSource,
  onOpenAll,
}: {
  sources: NonNullable<ChatMessage["sources"]>;
  onOpenSource?: (source: MessageSource) => void;
  onOpenAll?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const hasRag = sources.some((s) => s.kind === "rag");
  return (
    <div className="msg-ref">
      <button
        type="button"
        className={`msg-ref-toggle${open ? " is-open" : ""}`}
        onClick={() => setOpen((o) => !o)}
        title={`${sources.length} referência${sources.length > 1 ? "s" : ""}`}
        aria-label="Referências desta resposta"
        aria-expanded={open}
      >
        <QuoteIcon />
        <span className="msg-ref-count">{sources.length}</span>
      </button>
      {open ? (
        <div className="msg-ref-popover">
          <SourcesBlock
            sources={sources}
            onOpenSource={(s) => {
              setOpen(false);
              onOpenSource?.(s);
            }}
          />
          {hasRag && onOpenAll ? (
            <button
              type="button"
              className="msg-ref-open-all"
              onClick={() => {
                setOpen(false);
                onOpenAll();
              }}
            >
              Ver fontes no painel →
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function hostOf(url?: string): string {
  if (!url) return "";
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

function SourcesBlock({
  sources,
  onOpenSource,
}: {
  sources: NonNullable<ChatMessage["sources"]>;
  onOpenSource?: (source: MessageSource) => void;
}) {
  const hasWeb = sources.some((s) => s.kind === "web");
  const hasRag = sources.some((s) => s.kind === "rag");
  const title = hasWeb && hasRag ? "Fontes" : hasRag ? "Trechos do material" : "Fontes na web";

  return (
    <div className="msg-sources">
      <span className="msg-sources-title">{title}</span>
      <ol className="msg-sources-list">
        {sources.map((s, i) => {
          const inner = (
            <>
              <span className="msg-source-idx">{i + 1}</span>
              <span className="msg-source-text">
                <span className="msg-source-name">{s.title}</span>
                {s.kind === "web" && hostOf(s.url) ? (
                  <span className="msg-source-host">{hostOf(s.url)}</span>
                ) : s.kind === "rag" ? (
                  <span className="msg-source-host">
                    {s.page != null ? `página ${s.page}` : `trecho ${(s.chunk_index ?? 0) + 1}`}
                  </span>
                ) : null}
              </span>
            </>
          );
          return (
            <li key={i} className="msg-source">
              {s.kind === "web" && s.url ? (
                <a href={s.url} target="_blank" rel="noopener noreferrer" className="msg-source-link">
                  {inner}
                </a>
              ) : s.kind === "rag" ? (
                <button
                  type="button"
                  className="msg-source-link is-button"
                  onClick={() => onOpenSource?.(s)}
                  title="Ver o trecho no documento"
                >
                  {inner}
                </button>
              ) : (
                <span className="msg-source-link">{inner}</span>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
