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
import { AppShell } from "../layout/AppShell";
import { ExploreCenterColumn } from "./ExploreCenterColumn";
import { MemoryPanel } from "./MemoryPanel";
import { PlacePanel } from "./PlacePanel";
import { SetupOnboarding } from "./SetupOnboarding";

type PromptType = "notice" | "hope" | "fear";

export type ExploreModeProps = {
  needsOnboarding: boolean;
  pendingScene: boolean;
  backendNotice: string;
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
  history: WorldEvent[];
  facts: WorldEvent[];
  pendingSearch: boolean;
  onSearchFacts: (query: string) => Promise<void>;
  sceneText: string;
  draftSceneText: string;
  choices: Choice[];
  anyPending: boolean;
  turnPhase: TurnPhase;
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
  vars: VarsRecord;
  availableDirections: SpatialDirectionMap;
  leads: SpatialLead[];
  pendingMove: boolean;
  onMove: (direction: string) => void;
  showCompass: boolean;
  prefetchStatus: PrefetchStatusResponse | null;
  showPrefetchStatus: boolean;
};

export function ExploreMode({
  needsOnboarding,
  pendingScene,
  backendNotice,
  worldTheme,
  playerRole,
  noticeFirst,
  oneHope,
  oneFear,
  vibeLens,
  onWorldThemeChange,
  onPlayerRoleChange,
  onNoticeFirstChange,
  onOneHopeChange,
  onOneFearChange,
  onVibeLensChange,
  onOnboardingSubmit,
  history,
  facts,
  pendingSearch,
  onSearchFacts,
  sceneText,
  draftSceneText,
  choices,
  anyPending,
  turnPhase,
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
  vars,
  availableDirections,
  leads,
  pendingMove,
  onMove,
  showCompass,
  prefetchStatus,
  showPrefetchStatus,
}: ExploreModeProps) {
  if (needsOnboarding) {
    return (
      <SetupOnboarding
        pending={pendingScene}
        pendingNotice={backendNotice}
        worldTheme={worldTheme}
        playerRole={playerRole}
        noticeFirst={noticeFirst}
        oneHope={oneHope}
        oneFear={oneFear}
        vibeLens={vibeLens}
        onWorldThemeChange={onWorldThemeChange}
        onPlayerRoleChange={onPlayerRoleChange}
        onNoticeFirstChange={onNoticeFirstChange}
        onOneHopeChange={onOneHopeChange}
        onOneFearChange={onOneFearChange}
        onVibeLensChange={onVibeLensChange}
        onSubmit={onOnboardingSubmit}
      />
    );
  }

  return (
    <AppShell
      memoryPanel={
        <MemoryPanel
          events={history}
          facts={facts}
          searchPending={pendingSearch}
          onSearch={onSearchFacts}
        />
      }
      nowPanel={
        <ExploreCenterColumn
          sceneLane={{
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
          }}
          playerHintLane={{
            anyPending,
            longTurnPromptType,
            onLongTurnPromptTypeChange,
            longTurnPromptValue,
            onLongTurnPromptValueChange,
            onLongTurnPromptSubmit,
            longTurnVibe,
            onLongTurnVibeApply,
          }}
          changes={changes}
        />
      }
      placePanel={
        <PlacePanel
          vars={vars}
          availableDirections={availableDirections}
          leads={leads}
          pendingMove={pendingMove}
          onMove={onMove}
          showCompass={showCompass}
          prefetchStatus={prefetchStatus}
          showPrefetchStatus={showPrefetchStatus}
        />
      }
    />
  );
}
