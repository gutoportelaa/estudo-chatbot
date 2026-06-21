import { DEFAULT_COLOR_START, DEFAULT_COLOR_END } from "../hooks/useTheme";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  colorStart: string;
  colorEnd: string;
  setColorStart: (color: string) => void;
  setColorEnd: (color: string) => void;
}

interface Preset {
  name: string;
  start: string;
  end: string;
}

const PRESETS: Preset[] = [
  { name: "Verde (Padrão)", start: DEFAULT_COLOR_START, end: DEFAULT_COLOR_END },
  { name: "Pôr do Sol", start: "#FF5733", end: "#33C1FF" },
  { name: "Oceano", start: "#1FA2FF", end: "#12D8FA" },
  { name: "Âmbar", start: "#F7971E", end: "#FFD200" },
  { name: "Violeta", start: "#8E2DE2", end: "#4A00E0" },
  { name: "Rosa", start: "#F857A6", end: "#FF5858" },
];

export function PreferencesModal({
  isOpen,
  onClose,
  colorStart,
  colorEnd,
  setColorStart,
  setColorEnd,
}: Props) {
  if (!isOpen) return null;

  const isActive = (p: Preset) =>
    colorStart.toLowerCase() === p.start.toLowerCase() &&
    colorEnd.toLowerCase() === p.end.toLowerCase();

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Preferências</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Fechar" title="Fechar">
            ✕
          </button>
        </div>
        <div className="modal-body">
          <div className="prefs-section">
            <h3>Personalização de Tema</h3>
            <p className="prefs-desc">
              Escolha as cores do degradê que pinta o orbe, o ícone e os destaques da interface.
            </p>

            <div
              className="prefs-preview-orb"
              style={{
                background: `linear-gradient(165deg, ${colorEnd} 0%, ${colorStart} 30%, color-mix(in srgb, ${colorStart} 12%, #fff) 75%, #fff 100%)`,
              }}
              aria-hidden
            />

            <div className="color-pickers">
              <label className="color-field">
                <span>Cor Inicial</span>
                <div className="color-input-wrapper">
                  <input
                    type="color"
                    value={colorStart}
                    onChange={(e) => setColorStart(e.target.value)}
                  />
                  <span className="color-hex">{colorStart.toUpperCase()}</span>
                </div>
              </label>

              <label className="color-field">
                <span>Cor Final</span>
                <div className="color-input-wrapper">
                  <input
                    type="color"
                    value={colorEnd}
                    onChange={(e) => setColorEnd(e.target.value)}
                  />
                  <span className="color-hex">{colorEnd.toUpperCase()}</span>
                </div>
              </label>
            </div>

            <span className="prefs-presets-label">Paletas prontas</span>
            <div className="prefs-presets">
              {PRESETS.map((p) => (
                <button
                  key={p.name}
                  type="button"
                  className={`preset-card${isActive(p) ? " is-active" : ""}`}
                  onClick={() => {
                    setColorStart(p.start);
                    setColorEnd(p.end);
                  }}
                >
                  <span
                    className="preset-swatch"
                    style={{ background: `linear-gradient(135deg, ${p.start}, ${p.end})` }}
                  />
                  <span className="preset-name">{p.name}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
