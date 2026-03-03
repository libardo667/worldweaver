type LensSlidersProps = {
  values: Record<string, number>;
  onChange: (key: string, value: number) => void;
};

const LENS_DEFS: Array<{ key: string; label: string; hint: string }> = [
  { key: "lens.community", label: "Community", hint: "Belonging, trust, and social ties." },
  { key: "lens.mystery", label: "Mystery", hint: "Unknown clues, hidden motives, and riddles." },
  { key: "lens.wonder", label: "Wonder", hint: "Awe, discovery, and quiet revelation." },
];

function clampLensValue(value: number): number {
  if (!Number.isFinite(value)) {
    return 50;
  }
  return Math.max(0, Math.min(100, Math.round(value)));
}

export function LensSliders({ values, onChange }: LensSlidersProps) {
  return (
    <section className="panel create-panel">
      <header className="panel-header">
        <h3>Narrative Lenses</h3>
        <span className="panel-meta">Session vars: lens.*</span>
      </header>
      <div className="lens-stack">
        {LENS_DEFS.map((lens) => {
          const value = clampLensValue(values[lens.key] ?? 50);
          return (
            <label key={lens.key} className="lens-field">
              <div className="lens-header">
                <span>{lens.label}</span>
                <span className="lens-value">{value}</span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={value}
                onChange={(event) => onChange(lens.key, Number(event.target.value))}
              />
              <small className="muted">{lens.hint}</small>
            </label>
          );
        })}
      </div>
    </section>
  );
}
