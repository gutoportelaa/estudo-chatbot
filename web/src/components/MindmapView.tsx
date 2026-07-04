/**
 * MindmapView — mapas mentais no chat via Markmap (#36).
 * ---------------------------------------------------------------------------
 * A LLM produz apenas um **outline em markdown** (lista aninhada) — texto
 * determinístico, barato e cacheável. O Markmap transforma esse markdown numa
 * árvore e faz o auto-layout/render (D3), sem coordenadas nem schema JSON.
 *
 * Uso no chat: bloco ```markmap contendo o outline, ex.:
 *   # Fotossíntese
 *   ## Fase clara
 *   - Libera O₂
 *   ## Ciclo de Calvin
 *   - Produz glicose
 */

import { useEffect, useRef } from "react";
import { Transformer } from "markmap-lib";
import { Markmap } from "markmap-view";

const transformer = new Transformer();

export function MindmapView({ markdown }: { markdown: string }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const mmRef = useRef<Markmap | null>(null);

  useEffect(() => {
    if (!svgRef.current) return;
    if (!mmRef.current) {
      mmRef.current = Markmap.create(svgRef.current, {
        autoFit: true,
        duration: 200,
        paddingX: 16,
      });
    }
    const { root } = transformer.transform(markdown);
    mmRef.current.setData(root);
    void mmRef.current.fit();
  }, [markdown]);

  useEffect(() => {
    return () => {
      mmRef.current?.destroy();
      mmRef.current = null;
    };
  }, []);

  return (
    <div className="mindmap-view">
      <svg ref={svgRef} className="mindmap-svg" />
    </div>
  );
}
