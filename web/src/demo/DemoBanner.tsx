/**
 * Faixa que identifica a vitrine estática do GitHub Pages.
 * Deixa explícito para o visitante que não há backend nem LLM por trás.
 */

import { useEffect, useState } from "react";

const REPO = "https://github.com/gutoportelaa/estudo-chatbot";
const HEIGHT = 44;

export function DemoBanner() {
  const [open, setOpen] = useState(true);

  // `.app` ocupa 100vh; encolhe o layout enquanto a faixa estiver visível para
  // não cobrir o rodapé da barra lateral.
  useEffect(() => {
    const id = "demo-banner-style";
    let tag = document.getElementById(id) as HTMLStyleElement | null;
    if (!tag) {
      tag = document.createElement("style");
      tag.id = id;
      tag.textContent = ".app{height:calc(100vh - var(--demo-banner-h, 0px));}";
      document.head.appendChild(tag);
    }
    document.documentElement.style.setProperty("--demo-banner-h", open ? `${HEIGHT}px` : "0px");
  }, [open]);

  if (!open) return null;

  return (
    <div
      role="note"
      style={{
        position: "fixed",
        insetInline: 0,
        bottom: 0,
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 12,
        height: HEIGHT,
        padding: "0 16px",
        font: "500 13px/1.4 system-ui, sans-serif",
        color: "#f4f4f5",
        background: "rgba(24, 24, 27, 0.92)",
        backdropFilter: "blur(6px)",
        borderTop: "1px solid rgba(255,255,255,0.12)",
      }}
    >
      <span>
        <strong>Demonstração estática</strong> — sem backend ou modelo de linguagem. Os
        documentos, conversas e métricas são dados de exemplo.
      </span>
      <a
        href={REPO}
        target="_blank"
        rel="noopener noreferrer"
        style={{ color: "#4ade80", textDecoration: "underline", whiteSpace: "nowrap" }}
      >
        Ver o código
      </a>
      <button
        type="button"
        onClick={() => setOpen(false)}
        aria-label="Fechar aviso"
        style={{
          background: "transparent",
          border: 0,
          color: "inherit",
          cursor: "pointer",
          fontSize: 18,
          lineHeight: 1,
          padding: "0 4px",
        }}
      >
        ×
      </button>
    </div>
  );
}
