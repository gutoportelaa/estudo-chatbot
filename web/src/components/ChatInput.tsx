import { useRef, useState } from "react";
import { ImageIcon, PaperclipIcon, SendIcon } from "./icons";

interface Props {
  onSend: (text: string) => void;
  disabled: boolean;
  value: string;
  onChange: (v: string) => void;
}

export function ChatInput({ onSend, disabled, value, onChange }: Props) {
  const [tone, setTone] = useState("Formal");
  const taRef = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    if (!value.trim() || disabled) return;
    onSend(value);
    onChange("");
    if (taRef.current) taRef.current.style.height = "auto";
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const autoGrow = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
  };

  return (
    <div className="chat-input">
      <textarea
        ref={taRef}
        className="chat-textarea"
        placeholder="Como o ThinkAI pode te ajudar hoje?"
        value={value}
        onChange={autoGrow}
        onKeyDown={onKeyDown}
        rows={1}
      />
      <div className="chat-input-footer">
        <div className="chat-input-left">
          <span className="model-label">ThinkAI 3.5 Smart</span>
          <select
            className="tone-chip"
            value={tone}
            onChange={(e) => setTone(e.target.value)}
            aria-label="Tom da resposta"
          >
            <option>Formal</option>
            <option>Casual</option>
            <option>Neutro</option>
          </select>
        </div>
        <div className="chat-input-right">
          <button className="icon-btn ghost" aria-label="Anexar imagem">
            <ImageIcon />
          </button>
          <button className="icon-btn ghost" aria-label="Anexar arquivo">
            <PaperclipIcon />
          </button>
          <button
            className="send-btn"
            onClick={submit}
            disabled={disabled || !value.trim()}
            aria-label="Enviar"
          >
            <SendIcon />
          </button>
        </div>
      </div>
    </div>
  );
}
