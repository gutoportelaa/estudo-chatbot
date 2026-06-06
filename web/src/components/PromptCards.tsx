import { RefreshIcon } from "./icons";

const PROMPTS = [
  "Get fresh perspectives on tricky problems",
  "Brainstorm creative ideas",
  "Rewrite message for maximum impact",
  "Summarize key points",
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
      <button className="refresh-prompts" type="button">
        <RefreshIcon />
        Refresh prompts
      </button>
    </div>
  );
}
