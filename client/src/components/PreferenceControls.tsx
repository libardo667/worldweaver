type ToneOption = "cozy" | "tense" | "uncanny" | "hopeful";
type ViolenceLevel = "low" | "medium" | "high";
type RomanceToggle = "off" | "on";

type PreferenceControlsProps = {
  tone: ToneOption;
  violence: ViolenceLevel;
  romance: RomanceToggle;
  onToneChange: (value: ToneOption) => void;
  onViolenceChange: (value: ViolenceLevel) => void;
  onRomanceChange: (value: RomanceToggle) => void;
};

const TONE_OPTIONS: ToneOption[] = ["cozy", "tense", "uncanny", "hopeful"];
const VIOLENCE_OPTIONS: ViolenceLevel[] = ["low", "medium", "high"];
const ROMANCE_OPTIONS: RomanceToggle[] = ["off", "on"];

function renderOptionLabel(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function PreferenceControls({
  tone,
  violence,
  romance,
  onToneChange,
  onViolenceChange,
  onRomanceChange,
}: PreferenceControlsProps) {
  return (
    <section className="panel create-panel">
      <header className="panel-header">
        <h2>Create Preferences</h2>
        <span className="panel-meta">Steers, does not dictate</span>
      </header>

      <div className="create-field-group">
        <p className="create-label">Tone</p>
        <div className="create-chip-row" role="group" aria-label="Tone options">
          {TONE_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              className={`text-btn create-chip ${tone === option ? "active" : ""}`}
              onClick={() => onToneChange(option)}
            >
              {renderOptionLabel(option)}
            </button>
          ))}
        </div>
      </div>

      <div className="create-field-group">
        <p className="create-label">Violence boundary</p>
        <div className="create-chip-row" role="group" aria-label="Violence boundary">
          {VIOLENCE_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              className={`text-btn create-chip ${violence === option ? "active" : ""}`}
              onClick={() => onViolenceChange(option)}
            >
              {renderOptionLabel(option)}
            </button>
          ))}
        </div>
      </div>

      <div className="create-field-group">
        <p className="create-label">Romance</p>
        <div className="create-chip-row" role="group" aria-label="Romance boundary">
          {ROMANCE_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              className={`text-btn create-chip ${romance === option ? "active" : ""}`}
              onClick={() => onRomanceChange(option)}
            >
              {renderOptionLabel(option)}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

export type { ToneOption, ViolenceLevel, RomanceToggle };
