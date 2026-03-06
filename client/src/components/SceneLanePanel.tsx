import type { Choice, TurnPhase } from "../types";
import { FreeformInput } from "./FreeformInput";
import { NowPanel } from "./NowPanel";

export type SceneLanePanelProps = {
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
};

export function SceneLanePanel({
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
}: SceneLanePanelProps) {
  return (
    <>
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
    </>
  );
}
