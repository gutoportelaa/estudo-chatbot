/** Ícones SVG inline usados na interface (sem dependências externas). */

/**
 * Miniatura vetorial da logo ThinkAI — extraída dos 3 bolões do thinkai_logo.svg.
 * viewBox ajustado para enquadrar apenas as formas; degradê radial próprio de cada path.
 */
export function ThinkAILogo({ size = 22 }: { size?: number }) {
  const h = Math.round(size * 1.36);
  return (
    <svg
      width={size}
      height={h}
      viewBox="285 140 425 640"
      aria-hidden
      style={{ display: "block", flexShrink: 0 }}
    >
      <defs>
        {/* Degradê radial: centro claro → borda escura, aplicado ao bounding-box de cada path */}
        <radialGradient
          id="thinkai-rg"
          cx="42%"
          cy="38%"
          r="62%"
          gradientUnits="objectBoundingBox"
        >
          <stop offset="0%"   stopColor="#7de8a8" />
          <stop offset="55%"  stopColor="#2f9f56" />
          <stop offset="100%" stopColor="#145e2e" />
        </radialGradient>
      </defs>

      {/* bola_3 — superior direita */}
      <path
        d="M574.09,194.445C575.397,185.425 576.082,185.46 578.047,180.337C578.638,178.794
           582.444,168.873 588.567,162.56C589.867,161.22 599.045,151.757 606.69,147.876
           C650.613,125.578 690.084,152.986 700.051,187.654C703.967,201.274 701.403,214.342
           700.956,216.617C693.002,257.152 652.376,277.527 618.547,266.368
           C592.502,257.777 568.534,232.083 574.09,194.445Z"
        fill="url(#thinkai-rg)"
      />

      {/* bola_2 — meio esquerda */}
      <path
        d="M357.465,402.048C375.564,399.428 400.095,406.738 414.911,427.208
           C417.726,431.098 417.379,431.237 419.961,435.225C427.878,447.451 428.574,468.715
           426.325,478.45C416.382,521.477 371.877,540.997 335.736,523.039
           C314.543,512.509 304.08,491.542 301.705,480.438C292.92,439.364
           321.335,404.763 357.465,402.048Z"
        fill="url(#thinkai-rg)"
      />

      {/* bola_1 — inferior centro */}
      <path
        d="M509.501,623.051C546.571,621.968 579.793,656.616 571.817,698.549
           C562.72,746.378 502.76,769.682 463.535,729.466C447.596,713.124 433.869,671.781
           467.462,639.46C483.786,623.754 503.089,623.175 506.473,623.074
           C507.482,623.043 508.492,623.082 509.501,623.051Z"
        fill="url(#thinkai-rg)"
      />
    </svg>
  );
}

export function LogoIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="3" y="4" width="18" height="16" rx="3" stroke="currentColor" strokeWidth="1.8" />
      <path d="M12 4v16" stroke="currentColor" strokeWidth="1.8" />
      <path d="M7 9h2M7 13h2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function SunIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function MoonIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function RefreshIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M21 12a9 9 0 1 1-2.6-6.3M21 4v4h-4"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M5 12h14M13 6l6 6-6 6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function ImageIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="8.5" cy="9.5" r="1.5" fill="currentColor" />
      <path d="M21 16l-5-5-7 7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function MenuIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function ChatIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}

export function EllipsisIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M6 12h.01M12 12h.01M18 12h.01" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" />
    </svg>
  );
}

export function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M3 6h18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M8 6V4.5A1.5 1.5 0 0 1 9.5 3h5A1.5 1.5 0 0 1 16 4.5V6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M6 6l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M10 11v5M14 11v5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function PaperclipIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M21 11.5l-8.5 8.5a5 5 0 0 1-7-7L14 4.5a3.3 3.3 0 0 1 4.7 4.7l-8.5 8.5a1.7 1.7 0 0 1-2.3-2.3l7.8-7.8"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
