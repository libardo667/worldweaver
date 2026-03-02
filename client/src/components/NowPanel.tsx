import type { Choice } from "../types";
import { ChoiceButtons } from "./ChoiceButtons";

type NowPanelProps = {
  text: string;
  choices: Choice[];
  pending: boolean;
  onChoose: (choice: Choice) => void;
};

export function NowPanel({ text, choices, pending, onChoose }: NowPanelProps) {
  return (
    <section className="panel now-panel">
      <header className="panel-header">
        <h2>Now</h2>
        <span className="panel-meta">
          {pending ? "Resolving..." : `${choices.length} options`}
        </span>
      </header>
      <article className="scene-text">{text}</article>
      <ChoiceButtons choices={choices} disabled={pending} onChoose={onChoose} />
    </section>
  );
}
