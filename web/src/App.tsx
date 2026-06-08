import { useState } from "react";
import { ChatInput } from "./components/ChatInput";
import { Greeting } from "./components/Greeting";
import { Header } from "./components/Header";
import { MessageList } from "./components/MessageList";
import { PromptCards } from "./components/PromptCards";
import { useChat } from "./hooks/useChat";
import { useSession } from "./hooks/useSession";
import { useTheme } from "./hooks/useTheme";

export default function App() {
  const [theme, toggleTheme] = useTheme();
  const sessionId = useSession();
  const { messages, isStreaming, send } = useChat(sessionId);
  const [draft, setDraft] = useState("");

  const hasConversation = messages.length > 0;

  return (
    <div className="app">
      <div className="window">
        <Header theme={theme} onToggleTheme={toggleTheme} />

        <main className={`content ${hasConversation ? "is-chat" : "is-empty"}`}>
          {hasConversation ? (
            <MessageList messages={messages} />
          ) : (
            <div className="welcome">
              <Greeting />
              <PromptCards onPick={(p) => setDraft(p)} />
            </div>
          )}
        </main>

        <footer className="composer">
          <ChatInput
            value={draft}
            onChange={setDraft}
            onSend={send}
            disabled={isStreaming || !sessionId}
          />
          <div className="composer-footer">
            <span>O ThinkAI pode cometer erros. Verifique as respostas.</span>
            <span className="hint">
              Use <kbd>shift + return</kbd> para nova linha
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
}
