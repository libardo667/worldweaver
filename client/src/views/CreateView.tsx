import { LensSliders } from "../components/LensSliders";
import {
  PreferenceControls,
  type RomanceToggle,
  type ToneOption,
  type ViolenceLevel,
} from "../components/PreferenceControls";
import type { VarsRecord } from "../types";

type CreateViewProps = {
  vars: VarsRecord;
  pending: boolean;
  pendingNotice?: string;
  blockedByOnboarding: boolean;
  onSetVar: (key: string, value: string | number | boolean) => void;
  onSurpriseSafe: () => Promise<void>;
};

const TONE_OPTIONS = ["cozy", "tense", "uncanny", "hopeful"] as const;
const VIOLENCE_OPTIONS = ["low", "medium", "high"] as const;
const ROMANCE_OPTIONS = ["off", "on"] as const;

function readOption<T extends string>(
  vars: VarsRecord,
  key: string,
  allowed: readonly T[],
  fallback: T,
): T {
  const raw = vars[key];
  if (typeof raw !== "string") {
    return fallback;
  }
  return allowed.includes(raw as T) ? (raw as T) : fallback;
}

function readLensValue(vars: VarsRecord, key: string): number {
  const raw = vars[key];
  if (typeof raw !== "number" || !Number.isFinite(raw)) {
    return 50;
  }
  return Math.max(0, Math.min(100, Math.round(raw)));
}

function formatVarValue(value: unknown): string {
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? String(Math.round(value)) : "0";
  }
  if (typeof value === "string") {
    return value;
  }
  return "unset";
}

export function CreateView({
  vars,
  pending,
  pendingNotice = "",
  blockedByOnboarding,
  onSetVar,
  onSurpriseSafe,
}: CreateViewProps) {
  const tone = readOption<ToneOption>(vars, "pref.tone", TONE_OPTIONS, "cozy");
  const violence = readOption<ViolenceLevel>(
    vars,
    "pref.violence",
    VIOLENCE_OPTIONS,
    "medium",
  );
  const romance = readOption<RomanceToggle>(vars, "pref.romance", ROMANCE_OPTIONS, "off");

  const lensValues: Record<string, number> = {
    "lens.community": readLensValue(vars, "lens.community"),
    "lens.mystery": readLensValue(vars, "lens.mystery"),
    "lens.wonder": readLensValue(vars, "lens.wonder"),
  };

  const activeVars: Array<{ key: string; value: string }> = [
    { key: "pref.tone", value: formatVarValue(tone) },
    { key: "pref.violence", value: formatVarValue(violence) },
    { key: "pref.romance", value: formatVarValue(romance) },
    { key: "lens.community", value: formatVarValue(lensValues["lens.community"]) },
    { key: "lens.mystery", value: formatVarValue(lensValues["lens.mystery"]) },
    { key: "lens.wonder", value: formatVarValue(lensValues["lens.wonder"]) },
    { key: "surprise_safe", value: formatVarValue(vars.surprise_safe ?? false) },
  ];

  return (
    <main className="create-view" aria-label="Create mode">
      <section className="panel create-panel create-intro">
        <header className="panel-header">
          <h2>Create Mode</h2>
          <span className="panel-meta">Preference steering</span>
        </header>
        <p className="muted">
          Use these controls to steer tone and focus. They influence selection and prompts,
          but do not force outcomes.
        </p>
        {blockedByOnboarding ? (
          <p className="muted">
            Complete onboarding in Explore mode before running surprise actions.
          </p>
        ) : null}
        {pending && pendingNotice ? (
          <p className="backend-status-text" role="status" aria-live="polite">
            {pendingNotice}
          </p>
        ) : null}
      </section>

      <div className="create-prefs">
        <PreferenceControls
          tone={tone}
          violence={violence}
          romance={romance}
          onToneChange={(value) => onSetVar("pref.tone", value)}
          onViolenceChange={(value) => onSetVar("pref.violence", value)}
          onRomanceChange={(value) => onSetVar("pref.romance", value)}
        />
      </div>

      <div className="create-lenses">
        <LensSliders
          values={lensValues}
          onChange={(key, value) => onSetVar(key, value)}
        />
      </div>

      <section className="panel create-panel create-active">
        <header className="panel-header">
          <h3>Active Session Steering</h3>
          <span className="panel-meta">Mirrored into API vars</span>
        </header>
        <ul className="create-active-list">
          {activeVars.map((item) => (
            <li key={item.key}>
              <code>{item.key}</code>
              <span>{item.value}</span>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="choice-btn create-surprise-btn"
          onClick={() => void onSurpriseSafe()}
          disabled={pending || blockedByOnboarding}
          data-loading={pending ? "true" : "false"}
        >
          {pending ? "Weaving surprise..." : "Surprise me (safe)"}
        </button>
      </section>
    </main>
  );
}
