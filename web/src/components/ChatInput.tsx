import { useRef } from "react";
import { PaperclipIcon, SendIcon } from "./icons";

interface Props {
  onSend: (text: string) => void;
  disabled: boolean;
  value: string;
  onChange: (v: string) => void;
  modelName?: string;
  onAttach?: (file: File) => void | Promise<void>;
  attaching?: boolean;
  attachedCount?: number;
}

export function ChatInput({
  onSend,
  disabled,
  value,
  onChange,
  modelName,
  onAttach,
  attaching,
  attachedCount = 0,
}: Props) {
  const taRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

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
          {onAttach ? (
            <>
              <button
                className="icon-btn ghost"
                onClick={() => fileRef.current?.click()}
                disabled={disabled || attaching}
                aria-label="Anexar PDF à conversa"
                title={attaching ? "Anexando…" : "Anexar PDF à conversa"}
              >
                <PaperclipIcon />
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="application/pdf"
                hidden
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void onAttach(file);
                  e.target.value = "";
                }}
              />
            </>
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
