import type { ChangeItem, Choice, TurnPhase } from "../types";
import { FreeformInput } from "./FreeformInput";
import { NowPanel } from "./NowPanel";
import { WhatChangedStrip } from "./WhatChangedStrip";

type PromptType = "notice" | "hope" | "fear";

type ExploreCenterColumnProps = {
  sceneText: string;
  draftSceneText: string;
  choices: Choice[];
  anyPending: boolean;
  turnPhase: TurnPhase;
  backendNotice: string;
  onChoose: (choice: Choice) => void;
  pendingAction: boolean;
  onSubmitAction: (value: string) => Promise<void>;
  onTypingActivity: () => void;
  longTurnPromptType: PromptType;
  onLongTurnPromptTypeChange: (value: PromptType) => void;
  longTurnPromptValue: string;
  onLongTurnPromptValueChange: (value: string) => void;
  onLongTurnPromptSubmit: () => void;
  longTurnVibe: string;
  onLongTurnVibeApply: (value: string) => void;
  changes: ChangeItem[];
};

export function ExploreCenterColumn({
  sceneText,
  draftSceneText,
  choices,
  anyPending,
  turnPhase,
  backendNotice,
  onChoose,
  pendingAction,
  onSubmitAction,
  onTypingActivity,
  longTurnPromptType,
  onLongTurnPromptTypeChange,
  longTurnPromptValue,
  onLongTurnPromptValueChange,
  onLongTurnPromptSubmit,
  longTurnVibe,
  onLongTurnVibeApply,
  changes,
}: ExploreCenterColumnProps) {
  return (
    <section className="center-column">
      <NowPanel
        text={sceneText}
        draftText={draftSceneText}
        choices={choices}
        pending={anyPending}
        phase={turnPhase}
        backendNotice={backendNotice}
        onChoose={onChoose}
      />
      <FreeformInput
        pending={pendingAction}
        onSubmit={onSubmitAction}
        onTypingActivity={onTypingActivity}
      />
      {anyPending ? (
        <section className="panel weaving-prompts-inline">
          <header className="panel-header">
            <h3>World-Weaving Prompts</h3>
            <span className="panel-meta">Optional, non-blocking</span>
          </header>
          <p className="muted">
            Keep shaping tone while this turn resolves.
          </p>
          <div className="weaving-inline-row">
            <select
              aria-label="Prompt type"
              value={longTurnPromptType}
              onChange={(event) => {
                onLongTurnPromptTypeChange(event.target.value as PromptType);
              }}
            >
              <option value="notice">What do you notice first?</option>
              <option value="hope">Name one hope</option>
              <option value="fear">Name one fear</option>
            </select>
            <input
              type="text"
              value={longTurnPromptValue}
              maxLength={160}
              placeholder="Optional prompt answer"
              onChange={(event) => onLongTurnPromptValueChange(event.target.value)}
            />
            <button
              type="button"
              className="text-btn"
              onClick={onLongTurnPromptSubmit}
              disabled={!longTurnPromptValue.trim()}
            >
              Save prompt
            </button>
          </div>
          <div className="weaving-vibe-row">
            <span className="panel-meta">Vibe lens</span>
            {(["cozy", "tense", "uncanny", "hopeful"] as const).map((lens) => (
              <button
                key={lens}
                type="button"
                className={`text-btn ${longTurnVibe === lens ? "active-lens" : ""}`}
                onClick={() => onLongTurnVibeApply(lens)}
              >
                {lens}
              </button>
            ))}
          </div>
        </section>
      ) : null}
      <WhatChangedStrip changes={changes} pending={anyPending} phase={turnPhase} />
    </section>
  );
}
