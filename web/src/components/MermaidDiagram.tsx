import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

let initialized = false;
function ensureInitialized() {
  if (initialized) return;
  mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "neutral" });
  initialized = true;
}

let renderCounter = 0;

interface Props {
  mermaid: string;
  type: string;
}

/**
 * Renderiza um diagrama Mermaid como SVG. Se o parse/render falhar (mesmo com
 * a validação já feita no backend, o motor real do Mermaid roda só no
 * navegador), cai no fallback: mostra o texto bruto em vez de quebrar a UI.
 */
export function MermaidDiagram({ mermaid: code, type }: Props) {
  const [svg, setSvg] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const idRef = useRef(`diagram-${++renderCounter}`);

  useEffect(() => {
    let cancelled = false;
    ensureInitialized();

    async function render() {
      try {
        await mermaid.parse(code);
        const { svg: rendered } = await mermaid.render(idRef.current, code);
        if (!cancelled) setSvg(rendered);
      } catch {
        if (!cancelled) setFailed(true);
      }
    }

    void render();
    return () => {
      cancelled = true;
    };
  }, [code]);

  if (failed) {
    return (
      <pre className="diagram-fallback">
        <code>{code}</code>
      </pre>
    );
  }

  if (!svg) {
    return <div className="diagram-loading">Gerando diagrama ({type})…</div>;
  }

  return <div className="diagram-mermaid" dangerouslySetInnerHTML={{ __html: svg }} />;
}
