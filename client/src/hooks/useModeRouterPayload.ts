import { useMemo } from "react";

import type { ModeRouterPayload } from "../components/ModeRouter";

type ExplorePayload = ModeRouterPayload["explore"];
type PromptType = ExplorePayload["longTurnPromptType"];

type ExploreOnboardingContext = {
  needsOnboarding: ExplorePayload["needsOnboarding"];
  pendingScene: ExplorePayload["pendingScene"];
  backendNotice: ExplorePayload["backendNotice"];
  worldTheme: ExplorePayload["worldTheme"];
  playerRole: ExplorePayload["playerRole"];
  noticeFirst: ExplorePayload["noticeFirst"];
  oneHope: ExplorePayload["oneHope"];
  oneFear: ExplorePayload["oneFear"];
  vibeLens: ExplorePayload["vibeLens"];
  onWorldThemeChange: ExplorePayload["onWorldThemeChange"];
  onPlayerRoleChange: ExplorePayload["onPlayerRoleChange"];
  onNoticeFirstChange: ExplorePayload["onNoticeFirstChange"];
  onOneHopeChange: ExplorePayload["onOneHopeChange"];
  onOneFearChange: ExplorePayload["onOneFearChange"];
  onVibeLensChange: ExplorePayload["onVibeLensChange"];
  onOnboardingSubmit: ExplorePayload["onOnboardingSubmit"];
};

type ExploreMemoryContext = {
  history: ExplorePayload["history"];
  facts: ExplorePayload["facts"];
  pendingSearch: ExplorePayload["pendingSearch"];
  onSearchFacts: ExplorePayload["onSearchFacts"];
};

type ExploreSceneLaneContext = {
  sceneText: ExplorePayload["sceneText"];
  draftSceneText: ExplorePayload["draftSceneText"];
  choices: ExplorePayload["choices"];
  anyPending: ExplorePayload["anyPending"];
  turnPhase: ExplorePayload["turnPhase"];
  onChoose: ExplorePayload["onChoose"];
  pendingAction: ExplorePayload["pendingAction"];
  onSubmitAction: ExplorePayload["onSubmitAction"];
  onTypingActivity: ExplorePayload["onTypingActivity"];
};

type ExplorePlayerLaneContext = {
  longTurnPromptType: PromptType;
  onLongTurnPromptTypeChange: ExplorePayload["onLongTurnPromptTypeChange"];
  longTurnPromptValue: ExplorePayload["longTurnPromptValue"];
  onLongTurnPromptValueChange: ExplorePayload["onLongTurnPromptValueChange"];
  onLongTurnPromptSubmit: ExplorePayload["onLongTurnPromptSubmit"];
  longTurnVibe: ExplorePayload["longTurnVibe"];
  onLongTurnVibeApply: ExplorePayload["onLongTurnVibeApply"];
};

type ExplorePlaceLaneContext = {
  vars: ExplorePayload["vars"];
  availableDirections: ExplorePayload["availableDirections"];
  leads: ExplorePayload["leads"];
  pendingMove: ExplorePayload["pendingMove"];
  onMove: ExplorePayload["onMove"];
  showCompass: ExplorePayload["showCompass"];
  prefetchStatus: ExplorePayload["prefetchStatus"];
  showPrefetchStatus: ExplorePayload["showPrefetchStatus"];
};

export type UseModeRouterPayloadArgs = {
  explore: {
    onboarding: ExploreOnboardingContext;
    memory: ExploreMemoryContext;
    lanes: {
      scene: ExploreSceneLaneContext;
      player: ExplorePlayerLaneContext;
      place: ExplorePlaceLaneContext;
    };
    changes: ExplorePayload["changes"];
  };
  reflect: ModeRouterPayload["reflect"];
  create: ModeRouterPayload["create"];
  constellation: ModeRouterPayload["constellation"];
};

function buildExplorePayload(args: UseModeRouterPayloadArgs["explore"]): ExplorePayload {
  return {
    needsOnboarding: args.onboarding.needsOnboarding,
    pendingScene: args.onboarding.pendingScene,
    backendNotice: args.onboarding.backendNotice,
    worldTheme: args.onboarding.worldTheme,
    playerRole: args.onboarding.playerRole,
    noticeFirst: args.onboarding.noticeFirst,
    oneHope: args.onboarding.oneHope,
    oneFear: args.onboarding.oneFear,
    vibeLens: args.onboarding.vibeLens,
    onWorldThemeChange: args.onboarding.onWorldThemeChange,
    onPlayerRoleChange: args.onboarding.onPlayerRoleChange,
    onNoticeFirstChange: args.onboarding.onNoticeFirstChange,
    onOneHopeChange: args.onboarding.onOneHopeChange,
    onOneFearChange: args.onboarding.onOneFearChange,
    onVibeLensChange: args.onboarding.onVibeLensChange,
    onOnboardingSubmit: args.onboarding.onOnboardingSubmit,
    history: args.memory.history,
    facts: args.memory.facts,
    pendingSearch: args.memory.pendingSearch,
    onSearchFacts: args.memory.onSearchFacts,
    sceneText: args.lanes.scene.sceneText,
    draftSceneText: args.lanes.scene.draftSceneText,
    choices: args.lanes.scene.choices,
    anyPending: args.lanes.scene.anyPending,
    turnPhase: args.lanes.scene.turnPhase,
    onChoose: args.lanes.scene.onChoose,
    pendingAction: args.lanes.scene.pendingAction,
    onSubmitAction: args.lanes.scene.onSubmitAction,
    onTypingActivity: args.lanes.scene.onTypingActivity,
    longTurnPromptType: args.lanes.player.longTurnPromptType,
    onLongTurnPromptTypeChange: args.lanes.player.onLongTurnPromptTypeChange,
    longTurnPromptValue: args.lanes.player.longTurnPromptValue,
    onLongTurnPromptValueChange: args.lanes.player.onLongTurnPromptValueChange,
    onLongTurnPromptSubmit: args.lanes.player.onLongTurnPromptSubmit,
    longTurnVibe: args.lanes.player.longTurnVibe,
    onLongTurnVibeApply: args.lanes.player.onLongTurnVibeApply,
    changes: args.changes,
    vars: args.lanes.place.vars,
    availableDirections: args.lanes.place.availableDirections,
    leads: args.lanes.place.leads,
    pendingMove: args.lanes.place.pendingMove,
    onMove: args.lanes.place.onMove,
    showCompass: args.lanes.place.showCompass,
    prefetchStatus: args.lanes.place.prefetchStatus,
    showPrefetchStatus: args.lanes.place.showPrefetchStatus,
  };
}

export function useModeRouterPayload({
  explore,
  reflect,
  create,
  constellation,
}: UseModeRouterPayloadArgs): ModeRouterPayload {
  return useMemo(
    () => ({
      explore: buildExplorePayload(explore),
      reflect,
      create,
      constellation,
    }),
    [explore, reflect, create, constellation],
  );
}
