import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  fetchModelName,
  getSessionDocuments,
  type MessageSource,
} from "../api/client";
import { ChatInput } from "../components/ChatInput";
import { DocumentPanel } from "../components/DocumentPanel";
import { Greeting } from "../components/Greeting";
import { MemoryBadge } from "../components/MemoryBadge";
import { MessageList } from "../components/MessageList";
import { PromptCards } from "../components/PromptCards";
import { useChat } from "../hooks/useChat";

export function ChatPage() {
  const { sessionId = null } = useParams<{ sessionId: string }>();
  const { messages, isStreaming, send } = useChat(sessionId);
  const [draft, setDraft] = useState("");
  const [attachedIds, setAttachedIds] = useState<string[]>([]);
  const [panelSources, setPanelSources] = useState<MessageSource[] | null>(null);
  const [webSearch, setWebSearch] = useState(false);
  const [modelName, setModelName] = useState("");

  useEffect(() => {
    void fetchModelName().then(setModelName);
  }, []);

  useEffect(() => {
    if (!sessionId) {
      setAttachedIds([]);
      setPanelSources(null);
      return;
    }
    let active = true;
    getSessionDocuments(sessionId)
      .then((ids) => active && setAttachedIds(ids))
      .catch(() => active && setAttachedIds([]));
    setPanelSources(null);
    return () => {
      active = false;
    };
  }, [sessionId]);

  const hasConversation = messages.length > 0;
  const panelOpen = panelSources !== null;

  return (
    <div className={`window-body${panelOpen ? " has-panel" : ""}`}>
      <div className="chat-column">
        <main className={`content ${hasConversation ? "is-chat" : "is-empty"}`}>
          {hasConversation ? (
            <>
              <MemoryBadge sessionId={sessionId} refreshKey={messages.length} />
              <MessageList
                messages={messages}
                onOpenSource={(s) => {
                  const msg = messages.find((m) => (m.sources ?? []).includes(s));
                  setPanelSources((msg?.sources ?? [s]).filter((x) => x.kind === "rag"));
                }}
                onOpenSources={(list) =>
                  setPanelSources(list.filter((s) => s.kind === "rag"))
                }
              />
            </>
          ) : (
            <div className="welcome">
              <Greeting username="" />
              <PromptCards onPick={(p) => setDraft(p)} />
            </div>
          )}
        </main>

        <footer className="composer">
          <ChatInput
            value={draft}
            onChange={setDraft}
            onSend={(text) => {
              setDraft("");
              send(text, { webSearch });
            }}
            disabled={isStreaming || !sessionId}
            modelName={modelName}
            attachedCount={attachedIds.length}
            webSearch={webSearch}
            onToggleWebSearch={() => setWebSearch((v) => !v)}
          />
          <div className="composer-footer">
            <span>O ThinkAI pode cometer erros. Verifique as respostas.</span>
            <span className="hint">
              Use <kbd>shift + return</kbd> para nova linha
            </span>
          </div>
        </footer>
      </div>

      {panelOpen && panelSources ? (
        <DocumentPanel sources={panelSources} onClose={() => setPanelSources(null)} />
      ) : null}
    </div>
  );
}
