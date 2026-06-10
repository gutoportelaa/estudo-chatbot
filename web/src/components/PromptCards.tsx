// import { RefreshIcon } from "./icons";

const PROMPTS = [
  "Ter novas perspectivas sobre problemas difíceis",
  "Gerar ideias criativas",
  "Reescrever mensagem para maior impacto",
  "Resumir os pontos principais",
];

interface Props {
  onPick: (prompt: string) => void;
}

export function PromptCards({ onPick }: Props) {
  return (
    <div className="prompt-section">
      <div className="prompt-cards">
        {PROMPTS.map((p) => (
          <button key={p} className="prompt-card" onClick={() => onPick(p)}>
            {p}
          </button>
        ))}
      </div>
      {/* <button className="refresh-prompts" type="button">
        <RefreshIcon />
        Atualizar sugestões
      </button> */}
    </div>
  );
}
