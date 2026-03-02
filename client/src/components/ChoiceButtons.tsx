import type { Choice } from "../types";

type ChoiceButtonsProps = {
  choices: Choice[];
  disabled?: boolean;
  onChoose: (choice: Choice) => void;
};

export function ChoiceButtons({
  choices,
  disabled = false,
  onChoose,
}: ChoiceButtonsProps) {
  return (
    <div className="choice-grid" role="group" aria-label="Scene choices">
      {choices.map((choice, index) => (
        <button
          key={`${choice.label}-${index}`}
          type="button"
          className="choice-btn"
          disabled={disabled}
          onClick={() => onChoose(choice)}
        >
          {choice.label}
        </button>
      ))}
    </div>
  );
}
