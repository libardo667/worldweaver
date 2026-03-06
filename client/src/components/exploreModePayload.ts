import type {
  ChangeItem,
  Choice,
  PrefetchStatusResponse,
  SpatialDirectionMap,
  SpatialLead,
  TurnPhase,
  VarsRecord,
  WorldEvent,
} from "../types";

export type ExplorePromptType = "notice" | "hope" | "fear";

export type ExploreOnboardingPayload = {
  needsOnboarding: boolean;
  pendingScene: boolean;
  pendingNotice: string;
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
  onOnboardingSubmit: () => Promise<void>;
};

export type ExploreMemoryPayload = {
  history: WorldEvent[];
  facts: WorldEvent[];
  pendingSearch: boolean;
  onSearchFacts: (query: string) => Promise<void>;
};

export type ExploreSceneLanePayload = {
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

export type ExplorePlayerLanePayload = {
  anyPending: boolean;
  longTurnPromptType: ExplorePromptType;
  onLongTurnPromptTypeChange: (value: ExplorePromptType) => void;
  longTurnPromptValue: string;
  onLongTurnPromptValueChange: (value: string) => void;
  onLongTurnPromptSubmit: () => void;
  longTurnVibe: string;
  onLongTurnVibeApply: (value: string) => void;
};

export type ExplorePlaceLanePayload = {
  vars: VarsRecord;
  availableDirections: SpatialDirectionMap;
  leads: SpatialLead[];
  pendingMove: boolean;
  onMove: (direction: string) => void;
  showCompass: boolean;
  prefetchStatus: PrefetchStatusResponse | null;
  showPrefetchStatus: boolean;
};

export type ExploreModePayload = {
  onboarding: ExploreOnboardingPayload;
  memory: ExploreMemoryPayload;
  lanes: {
    scene: ExploreSceneLanePayload;
    player: ExplorePlayerLanePayload;
    place: ExplorePlaceLanePayload;
  };
  changes: ChangeItem[];
};

const PROMPT_TYPE_SET = new Set<ExplorePromptType>(["notice", "hope", "fear"]);

function normalizePromptType(value: ExplorePromptType): ExplorePromptType {
  const candidate = String(value ?? "").trim().toLowerCase();
  if (PROMPT_TYPE_SET.has(candidate as ExplorePromptType)) {
    return candidate as ExplorePromptType;
  }
  return "notice";
}

function normalizePrefetchStatus(
  value: PrefetchStatusResponse | null,
): PrefetchStatusResponse | null {
  if (!value) {
    return null;
  }
  const budgetMsRaw = value.budget_ms;
  const maxNodesRaw = value.max_nodes;
  const expansionDepthRaw = value.expansion_depth;
  return {
    stubs_cached: Math.max(0, Number(value.stubs_cached ?? 0) || 0),
    expires_in_seconds: Math.max(0, Number(value.expires_in_seconds ?? 0) || 0),
    ...(budgetMsRaw === undefined || budgetMsRaw === null
      ? {}
      : { budget_ms: Math.max(0, Number(budgetMsRaw) || 0) }),
    ...(maxNodesRaw === undefined || maxNodesRaw === null
      ? {}
      : { max_nodes: Math.max(0, Number(maxNodesRaw) || 0) }),
    ...(expansionDepthRaw === undefined || expansionDepthRaw === null
      ? {}
      : { expansion_depth: Math.max(0, Number(expansionDepthRaw) || 0) }),
  };
}

export function normalizeExploreModePayload(
  payload: ExploreModePayload,
): ExploreModePayload {
  const availableDirectionsCandidate = payload.lanes.place.availableDirections;
  const normalizedAvailableDirections =
    availableDirectionsCandidate
      && typeof availableDirectionsCandidate === "object"
      && !Array.isArray(availableDirectionsCandidate)
      ? availableDirectionsCandidate
      : ({} as SpatialDirectionMap);

  const varsCandidate = payload.lanes.place.vars;
  const normalizedVars =
    varsCandidate && typeof varsCandidate === "object" && !Array.isArray(varsCandidate)
      ? varsCandidate
      : ({} as VarsRecord);

  return {
    onboarding: {
      ...payload.onboarding,
      pendingNotice: String(payload.onboarding.pendingNotice ?? ""),
      worldTheme: String(payload.onboarding.worldTheme ?? ""),
      playerRole: String(payload.onboarding.playerRole ?? ""),
      noticeFirst: String(payload.onboarding.noticeFirst ?? ""),
      oneHope: String(payload.onboarding.oneHope ?? ""),
      oneFear: String(payload.onboarding.oneFear ?? ""),
      vibeLens: String(payload.onboarding.vibeLens ?? ""),
      needsOnboarding: Boolean(payload.onboarding.needsOnboarding),
      pendingScene: Boolean(payload.onboarding.pendingScene),
    },
    memory: {
      ...payload.memory,
      history: Array.isArray(payload.memory.history) ? payload.memory.history : [],
      facts: Array.isArray(payload.memory.facts) ? payload.memory.facts : [],
      pendingSearch: Boolean(payload.memory.pendingSearch),
    },
    lanes: {
      scene: {
        ...payload.lanes.scene,
        sceneText: String(payload.lanes.scene.sceneText ?? ""),
        draftSceneText: String(payload.lanes.scene.draftSceneText ?? ""),
        choices: Array.isArray(payload.lanes.scene.choices) ? payload.lanes.scene.choices : [],
        backendNotice: String(payload.lanes.scene.backendNotice ?? ""),
        anyPending: Boolean(payload.lanes.scene.anyPending),
        pendingAction: Boolean(payload.lanes.scene.pendingAction),
      },
      player: {
        ...payload.lanes.player,
        longTurnPromptType: normalizePromptType(payload.lanes.player.longTurnPromptType),
        longTurnPromptValue: String(payload.lanes.player.longTurnPromptValue ?? ""),
        longTurnVibe: String(payload.lanes.player.longTurnVibe ?? ""),
        anyPending: Boolean(payload.lanes.player.anyPending),
      },
      place: {
        ...payload.lanes.place,
        vars: normalizedVars,
        availableDirections: normalizedAvailableDirections,
        leads: Array.isArray(payload.lanes.place.leads) ? payload.lanes.place.leads : [],
        pendingMove: Boolean(payload.lanes.place.pendingMove),
        showCompass: Boolean(payload.lanes.place.showCompass),
        showPrefetchStatus: Boolean(payload.lanes.place.showPrefetchStatus),
        prefetchStatus: normalizePrefetchStatus(payload.lanes.place.prefetchStatus),
      },
    },
    changes: Array.isArray(payload.changes) ? payload.changes : [],
  };
}
