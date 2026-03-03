import { useEffect, useMemo, useRef } from "react";

import type { Choice, TurnPhase } from "../types";
import { ChoiceButtons } from "./ChoiceButtons";

type NowPanelProps = {
  text: string;
  draftText?: string;
  choices: Choice[];
  pending: boolean;
  phase: TurnPhase;
  backendNotice?: string;
  onChoose: (choice: Choice) => void;
};

function toPhaseLabel(phase: TurnPhase): string {
  if (phase === "interpreting") {
    return "Interpreting";
  }
  if (phase === "confirming") {
    return "Confirming";
  }
  if (phase === "rendering") {
    return "Rendering";
  }
  if (phase === "weaving_ahead") {
    return "Weaving ahead";
  }
  return "Idle";
}

export function NowPanel({
  text,
  draftText = "",
  choices,
  pending,
  phase,
  backendNotice = "",
  onChoose,
}: NowPanelProps) {
  const sceneRef = useRef<HTMLElement | null>(null);
  const stickToBottomRef = useRef(true);
  const phaseLabel = useMemo(() => toPhaseLabel(phase), [phase]);

  useEffect(() => {
    const node = sceneRef.current;
    if (!node || !stickToBottomRef.current) {
      return;
    }
    node.scrollTop = node.scrollHeight;
  }, [text, draftText]);

  function handleSceneScroll() {
    const node = sceneRef.current;
    if (!node) {
      return;
    }
    const distanceToBottom = node.scrollHeight - node.scrollTop - node.clientHeight;
    stickToBottomRef.current = distanceToBottom < 24;
  }

  return (
    <section className="panel now-panel">
      <header className="panel-header">
        <h2>Now</h2>
        <div className="now-status" aria-live="polite">
          <span className={`panel-meta ${pending ? "is-weaving" : ""}`}>
            {pending ? `Weaving... ${phaseLabel}` : `${choices.length} options`}
          </span>
          {pending ? (
            <span className="loading-pips" aria-hidden="true">
              <span className="loading-pip" />
              <span className="loading-pip" />
              <span className="loading-pip" />
            </span>
          ) : null}
        </div>
      </header>
      <div
        className={`now-loading-track ${pending ? "active" : ""}`}
        aria-hidden="true"
      >
        <span className="now-loading-bar" />
      </div>
      {pending && backendNotice ? (
        <p className="backend-status-text" role="status" aria-live="polite">
          {backendNotice}
        </p>
      ) : null}
      <article className="scene-text" ref={sceneRef} onScroll={handleSceneScroll}>
        <p className="scene-base-text">{text}</p>
        {pending && draftText ? (
          <p className="scene-draft-text" aria-live="polite">
            <strong>In progress:</strong> {draftText}
          </p>
        ) : null}
      </article>
      <ChoiceButtons choices={choices} disabled={pending} onChoose={onChoose} />
    </section>
  );
}
