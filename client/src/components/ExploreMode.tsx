import { AppShell } from "../layout/AppShell";
import { ExploreCenterColumn } from "./ExploreCenterColumn";
import { MemoryPanel } from "./MemoryPanel";
import { PlacePanel } from "./PlacePanel";
import { SetupOnboarding } from "./SetupOnboarding";
import type { ExploreModePayload } from "./exploreModePayload";

export type ExploreModeProps = {
  payload: ExploreModePayload;
};

export function ExploreMode({ payload }: ExploreModeProps) {
  if (payload.onboarding.needsOnboarding) {
    return (
      <SetupOnboarding
        pending={payload.onboarding.pendingScene}
        pendingNotice={payload.onboarding.pendingNotice}
        worldTheme={payload.onboarding.worldTheme}
        playerRole={payload.onboarding.playerRole}
        noticeFirst={payload.onboarding.noticeFirst}
        oneHope={payload.onboarding.oneHope}
        oneFear={payload.onboarding.oneFear}
        vibeLens={payload.onboarding.vibeLens}
        onWorldThemeChange={payload.onboarding.onWorldThemeChange}
        onPlayerRoleChange={payload.onboarding.onPlayerRoleChange}
        onNoticeFirstChange={payload.onboarding.onNoticeFirstChange}
        onOneHopeChange={payload.onboarding.onOneHopeChange}
        onOneFearChange={payload.onboarding.onOneFearChange}
        onVibeLensChange={payload.onboarding.onVibeLensChange}
        onSubmit={payload.onboarding.onOnboardingSubmit}
      />
    );
  }

  return (
    <AppShell
      memoryPanel={
        <MemoryPanel
          events={payload.memory.history}
          facts={payload.memory.facts}
          searchPending={payload.memory.pendingSearch}
          onSearch={payload.memory.onSearchFacts}
        />
      }
      nowPanel={
        <ExploreCenterColumn
          sceneLane={{
            sceneText: payload.lanes.scene.sceneText,
            draftSceneText: payload.lanes.scene.draftSceneText,
            choices: payload.lanes.scene.choices,
            anyPending: payload.lanes.scene.anyPending,
            turnPhase: payload.lanes.scene.turnPhase,
            backendNotice: payload.lanes.scene.backendNotice,
            onChoose: payload.lanes.scene.onChoose,
            pendingAction: payload.lanes.scene.pendingAction,
            onSubmitAction: payload.lanes.scene.onSubmitAction,
            onTypingActivity: payload.lanes.scene.onTypingActivity,
          }}
          playerHintLane={{
            anyPending: payload.lanes.player.anyPending,
            longTurnPromptType: payload.lanes.player.longTurnPromptType,
            onLongTurnPromptTypeChange: payload.lanes.player.onLongTurnPromptTypeChange,
            longTurnPromptValue: payload.lanes.player.longTurnPromptValue,
            onLongTurnPromptValueChange: payload.lanes.player.onLongTurnPromptValueChange,
            onLongTurnPromptSubmit: payload.lanes.player.onLongTurnPromptSubmit,
            longTurnVibe: payload.lanes.player.longTurnVibe,
            onLongTurnVibeApply: payload.lanes.player.onLongTurnVibeApply,
          }}
          changes={payload.changes}
        />
      }
      placePanel={
        <PlacePanel
          vars={payload.lanes.place.vars}
          availableDirections={payload.lanes.place.availableDirections}
          leads={payload.lanes.place.leads}
          pendingMove={payload.lanes.place.pendingMove}
          onMove={payload.lanes.place.onMove}
          showCompass={payload.lanes.place.showCompass}
          prefetchStatus={payload.lanes.place.prefetchStatus}
          showPrefetchStatus={payload.lanes.place.showPrefetchStatus}
        />
      }
    />
  );
}
