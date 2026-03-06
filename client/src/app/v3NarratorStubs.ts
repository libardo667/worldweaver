import type { Choice, V3TurnMetadata, VarsRecord } from "../types";

export type NarratorLane = "world" | "scene" | "player";

export type NarratorOperationKind =
  | "bootstrap"
  | "onboarding"
  | "choice"
  | "action"
  | "move"
  | "reset";

export type NarratorTurnOperation = Extract<
  NarratorOperationKind,
  "choice" | "action" | "move"
>;

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
  lane: NarratorLane;
  operation: NarratorOperationKind;
  sessionId: string;
  ok: boolean;
  nextVars?: VarsRecord;
  choices?: Choice[];
  v3Metadata?: V3TurnMetadata | null;
};

export interface V3NarratorLaneAdapter {
  beforeTurn?(context: NarratorTurnContext): string | null;
  afterTurn?(result: NarratorTurnResult): void;
}

// V3 anchor: explicit extension points for world/scene/player narrator lanes.
export interface V3NarratorHooks {
  lanes: Record<NarratorLane, V3NarratorLaneAdapter>;
}

function createNoopLaneAdapter(): V3NarratorLaneAdapter {
  return {
    beforeTurn: () => null,
    afterTurn: () => {
      // Intentionally no-op in v2 runtime; used as a V3 integration seam.
    },
  };
}

export const v3NarratorHooksStub: V3NarratorHooks = {
  lanes: {
    world: createNoopLaneAdapter(),
    scene: createNoopLaneAdapter(),
    player: createNoopLaneAdapter(),
  },
};

const SCENE_LANE_DEFAULT_NOTICES: Record<NarratorTurnOperation, string> = {
  choice: "Scene lane: applying your choice and weaving the next storylet...",
  action: "Scene lane: interpreting your action and resolving world consequences...",
  move: "Scene lane: validating movement and fetching the destination storylet...",
};

export function getSceneLaneDefaultNotice(
  operation: NarratorTurnOperation,
): string {
  return SCENE_LANE_DEFAULT_NOTICES[operation];
}

export function getNarratorLaneAdapter(
  hooks: V3NarratorHooks | undefined,
  lane: NarratorLane,
): V3NarratorLaneAdapter {
  return hooks?.lanes[lane] ?? v3NarratorHooksStub.lanes[lane];
}
