import { useRef } from "react";
import { PaperclipIcon, SendIcon } from "./icons";

interface Props {
  onSend: (text: string) => void;
  disabled: boolean;
  value: string;
  onChange: (v: string) => void;
  modelName?: string;
  onOpenAttach?: () => void;
  attachedCount?: number;
}

export function ChatInput({
  onSend,
  disabled,
  value,
  onChange,
  modelName,
  onOpenAttach,
  attachedCount = 0,
}: Props) {
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
          <span className="model-label">{modelName || "—"}</span>
          {attachedCount > 0 ? (
            <span className="attach-chip" title="Documentos nesta conversa">
              <PaperclipIcon /> {attachedCount}
            </span>
          ) : null}
        </div>
        <div className="chat-input-right">
          {onOpenAttach ? (
            <button
              className="icon-btn ghost"
              onClick={onOpenAttach}
              aria-label="Abrir documentos da conversa"
              title="Documentos da conversa"
            >
              <PaperclipIcon />
            </button>
          ) : null}
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
