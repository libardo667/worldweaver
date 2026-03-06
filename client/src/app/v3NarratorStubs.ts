import type { Choice, VarsRecord } from "../types";

export type NarratorLane = "world" | "scene" | "player";

export type NarratorOperationKind =
  | "bootstrap"
  | "onboarding"
  | "choice"
  | "action"
  | "move"
  | "reset";

export type NarratorTurnContext = {
  lane: NarratorLane;
  operation: NarratorOperationKind;
  sessionId: string;
  vars: VarsRecord;
  actionText?: string;
  choiceLabel?: string;
  direction?: string;
};

export type NarratorTurnResult = {
  operation: NarratorOperationKind;
  sessionId: string;
  ok: boolean;
  nextVars?: VarsRecord;
  choices?: Choice[];
};

// V3 anchor: explicit extension points for world/scene/player narrator lanes.
export interface V3NarratorHooks {
  beforeTurn(context: NarratorTurnContext): string | null;
  afterTurn(result: NarratorTurnResult): void;
}

export const v3NarratorHooksStub: V3NarratorHooks = {
  beforeTurn: () => null,
  afterTurn: () => {
    // Intentionally no-op in v2 runtime; used as a V3 integration seam.
  },
};
