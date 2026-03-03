import type { FormEvent } from "react";

type SetupOnboardingProps = {
  pending: boolean;
  worldTheme: string;
  playerRole: string;
  noticeFirst: string;
  oneHope: string;
  oneFear: string;
  vibeLens: string;
  onWorldThemeChange: (value: string) => void;
  onPlayerRoleChange: (value: string) => void;
  onNoticeFirstChange: (value: string) => void;
  onOneHopeChange: (value: string) => void;
  onOneFearChange: (value: string) => void;
  onVibeLensChange: (value: string) => void;
  onSubmit: () => Promise<void>;
};

export function SetupOnboarding({
  pending,
  worldTheme,
  playerRole,
  noticeFirst,
  oneHope,
  oneFear,
  vibeLens,
  onWorldThemeChange,
  onPlayerRoleChange,
  onNoticeFirstChange,
  onOneHopeChange,
  onOneFearChange,
  onVibeLensChange,
  onSubmit,
}: SetupOnboardingProps) {
  const canShowPromptFields = worldTheme.trim().length > 0 && playerRole.trim().length > 0;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit();
  }

  return (
    <section className="panel setup-shell" aria-live="polite">
      <header className="panel-header">
        <h2>Before We Begin</h2>
        <span className="panel-meta">Vision-guided onboarding</span>
      </header>
      <p className="muted">
        Define your starting theme and character first. Optional weaving prompts help
        shape lens weighting while the world warms up.
      </p>
      <form className="setup-form" onSubmit={handleSubmit}>
        <label className="setup-field">
          What kind of world theme do you want to explore?
          <input
            type="text"
            value={worldTheme}
            maxLength={120}
            placeholder="e.g. frontier mystery, occult city noir, hopeful solarpunk"
            onChange={(event) => onWorldThemeChange(event.target.value)}
          />
        </label>
        <label className="setup-field">
          Who are you in this world?
          <input
            type="text"
            value={playerRole}
            maxLength={120}
            placeholder="e.g. exiled cartographer, apprentice witch, retired ranger"
            onChange={(event) => onPlayerRoleChange(event.target.value)}
          />
        </label>

        {canShowPromptFields ? (
          <fieldset className="setup-prompts">
            <legend>Optional world-weaving prompts</legend>
            <label className="setup-field">
              What do you notice first?
              <input
                type="text"
                value={noticeFirst}
                maxLength={160}
                placeholder="A detail that immediately stands out."
                onChange={(event) => onNoticeFirstChange(event.target.value)}
              />
            </label>
            <label className="setup-field">
              Name one hope.
              <input
                type="text"
                value={oneHope}
                maxLength={160}
                placeholder="What are you hoping for in this world?"
                onChange={(event) => onOneHopeChange(event.target.value)}
              />
            </label>
            <label className="setup-field">
              Name one fear.
              <input
                type="text"
                value={oneFear}
                maxLength={160}
                placeholder="What feels risky or unsettling?"
                onChange={(event) => onOneFearChange(event.target.value)}
              />
            </label>
            <label className="setup-field">
              Pick a vibe lens.
              <select
                value={vibeLens}
                onChange={(event) => onVibeLensChange(event.target.value)}
              >
                <option value="">No lens</option>
                <option value="cozy">Cozy</option>
                <option value="tense">Tense</option>
                <option value="uncanny">Uncanny</option>
                <option value="hopeful">Hopeful</option>
              </select>
            </label>
          </fieldset>
        ) : null}

        <button type="submit" className="choice-btn setup-submit" disabled={pending}>
          Start this world
        </button>
      </form>
    </section>
  );
}

