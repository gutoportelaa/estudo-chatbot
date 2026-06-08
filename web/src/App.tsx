import { useState } from "react";
import { AuthPage } from "./components/AuthPage";
import { ChatInput } from "./components/ChatInput";
import { Greeting } from "./components/Greeting";
import { Header } from "./components/Header";
import { MessageList } from "./components/MessageList";
import { PromptCards } from "./components/PromptCards";
import { useAuth } from "./hooks/useAuth";
import { useChat } from "./hooks/useChat";
import { useSession } from "./hooks/useSession";
import { useTheme } from "./hooks/useTheme";

export default function App() {
  const [theme, toggleTheme] = useTheme();
  const auth = useAuth();
  const sessionId = useSession(auth.token);
  const { messages, isStreaming, send } = useChat(auth.token, sessionId);
  const [draft, setDraft] = useState("");

  if (!auth.token) {
    return <AuthPage auth={auth} />;
  }

  const hasConversation = messages.length > 0;

  const handleSend = (text: string) => {
    setDraft("");
    send(text);
  };

  return (
    <div className="app">
      <div className="window">
        <Header theme={theme} onToggleTheme={toggleTheme} username={auth.username} onLogout={auth.logout} />

        <main className={`content ${hasConversation ? "is-chat" : "is-empty"}`}>
          {hasConversation ? (
            <MessageList messages={messages} />
          ) : (
            <div className="welcome">
              <Greeting username={auth.username} />
              <PromptCards onPick={handleSend} />
            </div>
          )}
        </main>

        <footer className="composer">
          <ChatInput
            value={draft}
            onChange={setDraft}
            onSend={handleSend}
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
