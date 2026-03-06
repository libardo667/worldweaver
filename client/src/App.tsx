import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getSettingsReadiness,
  getSpatialNavigation,
  getWorldFacts,
  getWorldHistory,
  postNext,
} from "./api/wwClient";
import { v3NarratorHooksStub } from "./app/v3NarratorStubs";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { SetupModal } from "./components/SetupModal";
import { AppTopbar } from "./components/AppTopbar";
import { ErrorToastStack } from "./components/ErrorToastStack";
import { ModeRouter, type ModeRouterPayload } from "./components/ModeRouter";
import { usePrefetchFrontier } from "./hooks/usePrefetchFrontier";
import { useSessionLifecycle } from "./hooks/useSessionLifecycle";
import { useTurnOrchestration } from "./hooks/useTurnOrchestration";
import { buildWhatChangedReceipts } from "./utils/diffVars";
import {
  buildTopbarRuntimeStatus,
  ENABLE_ASSISTIVE_SPATIAL,
  ENABLE_CONSTELLATION,
  ENABLE_DEV_RESET,
  makeId,
  normalizeVars,
  PLACE_REFRESH_NOTICE,
  PLACE_REFRESH_NOTICE_COOLDOWN_MS,
  PLAYER_ROLE_KEY,
  PROMPT_FEAR_KEY,
  PROMPT_HOPE_KEY,
  PROMPT_NOTICE_KEY,
  PROMPT_VIBE_KEY,
  readStringVar,
  SHOW_PREFETCH_STATUS,
  SURPRISE_SAFE_ACTION,
  toAccessibleDirectionMap,
  toNextPayloadVars,
  WORLD_THEME_KEY,
  type ClientMode,
} from "./app/appHelpers";
import {
  getOnboardedSessionId,
  getOrCreateSessionId,
  loadSessionVars,
  saveSessionVars,
} from "./state/sessionStore";
import type {
  ChangeItem,
  Choice,
  SettingsReadinessResponse,
  SpatialDirectionMap,
  TurnPhase,
  ToastItem,
  VarsRecord,
  WorldEvent,
} from "./types";

export default function App() {
  const [mode, setMode] = useState<ClientMode>("explore");
  const [sessionId, setSessionId] = useState<string>(() => getOrCreateSessionId());
  const [vars, setVars] = useState<VarsRecord>(() => loadSessionVars());
  const [sceneText, setSceneText] = useState<string>("Weaving the world around you...");
  const [draftSceneText, setDraftSceneText] = useState<string>("");
  const [choices, setChoices] = useState<Choice[]>([]);
  const [availableDirections, setAvailableDirections] = useState<SpatialDirectionMap>({});
  const [leads, setLeads] = useState<Array<{ direction: string; title: string; score: number }>>([]);
  const [history, setHistory] = useState<WorldEvent[]>([]);
  const [facts, setFacts] = useState<WorldEvent[]>([]);
  const [changes, setChanges] = useState<ChangeItem[]>([]);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [pendingScene, setPendingScene] = useState(false);
  const [pendingAction, setPendingAction] = useState(false);
  const [pendingMove, setPendingMove] = useState(false);
  const [pendingSearch, setPendingSearch] = useState(false);
  const [pendingHistory, setPendingHistory] = useState(false);
  const [turnPhase, setTurnPhase] = useState<TurnPhase>("idle");
  const [backendNotice, setBackendNotice] = useState("");
  const [historyLimit, setHistoryLimit] = useState(60);
  const [worldThemeInput, setWorldThemeInput] = useState<string>(() => readStringVar(vars, WORLD_THEME_KEY));
  const [characterInput, setCharacterInput] = useState<string>(() => readStringVar(vars, PLAYER_ROLE_KEY));
  const [noticeFirstInput, setNoticeFirstInput] = useState<string>(
    () => readStringVar(vars, PROMPT_NOTICE_KEY),
  );
  const [oneHopeInput, setOneHopeInput] = useState<string>(() => readStringVar(vars, PROMPT_HOPE_KEY));
  const [oneFearInput, setOneFearInput] = useState<string>(() => readStringVar(vars, PROMPT_FEAR_KEY));
  const [vibeLensInput, setVibeLensInput] = useState<string>(() => readStringVar(vars, PROMPT_VIBE_KEY));
  const [longTurnPromptType, setLongTurnPromptType] = useState<"notice" | "hope" | "fear">("notice");
  const [longTurnPromptValue, setLongTurnPromptValue] = useState("");
  const [longTurnVibe, setLongTurnVibe] = useState<string>(() => readStringVar(vars, PROMPT_VIBE_KEY));
  const [needsOnboarding, setNeedsOnboarding] = useState<boolean>(
    () => getOnboardedSessionId() !== sessionId,
  );
  const [bootstrapNonce, setBootstrapNonce] = useState(0);
  const [settingsReadiness, setSettingsReadiness] = useState<SettingsReadinessResponse | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const latestSessionId = useRef(sessionId);
  const actionStreamAbortRef = useRef<AbortController | null>(null);
  const bootstrappedSceneKeyRef = useRef("");
  const lastBlockedMoveToastAtRef = useRef(0);
  const lastPlaceRefreshToastAtRef = useRef(0);

  const pushToast = useCallback((title: string, detail?: string, kind: ToastItem["kind"] = "error") => {
    const toast: ToastItem = { id: makeId("toast"), title, detail, kind };
    setToasts((prev) => [toast, ...prev].slice(0, 4));
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const {
    prefetchStatus,
    notifyTypingActivity,
    scheduleScenePrefetch,
    triggerPrefetch,
  } = usePrefetchFrontier({
    sessionId,
    enabled: !needsOnboarding,
    onSoftError: (detail) => {
      pushToast("Weaving ahead delayed.", detail, "info");
    },
  });

  const anyPending = pendingScene || pendingAction || pendingMove;
  const anyBusy = anyPending || pendingSearch || pendingHistory;
  const topbarRuntimeStatus = useMemo(
    () => buildTopbarRuntimeStatus({
      anyBusy,
      backendNotice,
      pendingScene,
      pendingAction,
      pendingMove,
      prefetchStatus,
      needsOnboarding,
    }),
    [
      anyBusy,
      backendNotice,
      needsOnboarding,
      pendingAction,
      pendingMove,
      pendingScene,
      prefetchStatus,
    ],
  );

  useEffect(() => {
    setNeedsOnboarding(getOnboardedSessionId() !== sessionId);
  }, [sessionId]);

  useEffect(() => {
    latestSessionId.current = sessionId;
  }, [sessionId]);

  function isStaleSession(requestSessionId: string): boolean {
    return latestSessionId.current !== requestSessionId;
  }

  function persistVars(nextVars: VarsRecord) {
    setVars(nextVars);
    saveSessionVars(nextVars);
  }

  function applyPromptPatch(patch: VarsRecord, eventLabel: string) {
    const previousVars = vars;
    const nextVars = { ...previousVars, ...patch };
    persistVars(nextVars);
    setChanges(
      buildWhatChangedReceipts({
        eventLabel,
        previousVars,
        nextVars,
        stateChanges: patch,
      }),
    );
  }

  function applyReplacementSessionState({
    replacementSessionId,
    nextSceneText,
    changeText,
  }: {
    replacementSessionId: string;
    nextSceneText: string;
    changeText: string;
  }) {
    latestSessionId.current = replacementSessionId;
    setMode("explore");
    setSessionId(replacementSessionId);
    setSceneText(nextSceneText);
    setChoices([]);
    setHistory([]);
    setFacts([]);
    setAvailableDirections({});
    setLeads([]);
    setHistoryLimit(60);
    setChanges([{ id: makeId("evt"), text: changeText }]);
    persistVars({});
    setWorldThemeInput("");
    setCharacterInput("");
    setNoticeFirstInput("");
    setOneHopeInput("");
    setOneFearInput("");
    setVibeLensInput("");
    setLongTurnPromptValue("");
    setLongTurnVibe("");
    setNeedsOnboarding(true);
    setBootstrapNonce((value) => value + 1);
  }

  function beginTurnOperation({
    notice,
    phase,
    setPending,
  }: {
    notice: string;
    phase: TurnPhase;
    setPending: (value: boolean) => void;
  }) {
    setBackendNotice(notice);
    setPending(true);
    setTurnPhase(phase);
    setDraftSceneText("");
  }

  function finishTurnOperation(setPending: (value: boolean) => void) {
    setPending(false);
    setTurnPhase("idle");
    setDraftSceneText("");
    setBackendNotice("");
  }

  const refreshReadiness = useCallback(async () => {
    try {
      const readiness = await getSettingsReadiness();
      setSettingsReadiness(readiness);
    } catch (err) {
      console.warn("Could not check settings readiness", err);
    }
  }, []);

  useEffect(() => {
    void refreshReadiness();
  }, [refreshReadiness]);

  async function refreshMemory(limit = historyLimit, requestSessionId = sessionId) {
    setPendingHistory(true);
    try {
      const memory = await getWorldHistory(requestSessionId, limit);
      if (isStaleSession(requestSessionId)) {
        return;
      }
      setHistory(memory.events ?? []);
      setHistoryLimit(limit);
    } catch (error) {
      if (isStaleSession(requestSessionId)) {
        return;
      }
      pushToast("Memory shimmered and blurred.", String(error));
    } finally {
      if (!isStaleSession(requestSessionId)) {
        setPendingHistory(false);
      }
    }
  }

  async function refreshPlace(
    requestSessionId = sessionId,
    options: { bestEffort?: boolean } = {},
  ) {
    if (!ENABLE_ASSISTIVE_SPATIAL) {
      if (!isStaleSession(requestSessionId)) {
        setAvailableDirections({});
        setLeads([]);
      }
      return;
    }
    const { bestEffort = false } = options;
    try {
      const spatial = await getSpatialNavigation(requestSessionId);
      if (isStaleSession(requestSessionId)) {
        return;
      }
      setAvailableDirections(
        Object.keys(spatial.available_directions ?? {}).length > 0
          ? spatial.available_directions
          : toAccessibleDirectionMap(spatial.directions ?? []),
      );
      setLeads(spatial.leads ?? []);
    } catch (error) {
      if (isStaleSession(requestSessionId)) {
        return;
      }
      if (bestEffort) {
        const now = Date.now();
        if (now - lastPlaceRefreshToastAtRef.current >= PLACE_REFRESH_NOTICE_COOLDOWN_MS) {
          lastPlaceRefreshToastAtRef.current = now;
          pushToast("Place panel update delayed.", PLACE_REFRESH_NOTICE, "info");
        }
        return;
      }
      pushToast("Could not read nearby paths.", String(error), "info");
    }
  }

  function scheduleBestEffortPlaceRefresh(requestSessionId = sessionId) {
    window.setTimeout(() => {
      if (isStaleSession(requestSessionId)) {
        return;
      }
      void refreshPlace(requestSessionId, { bestEffort: true });
    }, 0);
  }

  const {
    refreshPostTurnContext,
    fetchScene,
    handleChoice,
    handleAction,
    handleMove,
  } = useTurnOrchestration({
    sessionId,
    vars,
    historyLimit,
    enableAssistiveSpatial: ENABLE_ASSISTIVE_SPATIAL,
    isStaleSession,
    persistVars,
    pushToast,
    setSceneText,
    setChoices,
    setTurnPhase,
    setDraftSceneText,
    setChanges,
    setPendingScene,
    setPendingAction,
    setPendingMove,
    beginTurnOperation,
    finishTurnOperation,
    refreshMemory,
    scheduleBestEffortPlaceRefresh,
    actionStreamAbortRef,
    lastBlockedMoveToastAtRef,
    narratorHooks: v3NarratorHooksStub,
  });

  const {
    handleOnboardingSubmit,
    handleResetSession,
    handleDevHardReset,
  } = useSessionLifecycle({
    sessionId,
    vars,
    worldThemeInput,
    characterInput,
    noticeFirstInput,
    oneHopeInput,
    oneFearInput,
    vibeLensInput,
    beginTurnOperation,
    finishTurnOperation,
    setPendingScene,
    isStaleSession,
    persistVars,
    setLongTurnVibe,
    setNeedsOnboarding,
    setSceneText,
    setTurnPhase,
    setChanges,
    setBootstrapNonce,
    triggerPrefetch,
    pushToast,
    actionStreamAbortRef,
    bootstrappedSceneKeyRef,
    applyReplacementSessionState,
    refreshReadiness,
  });

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      if (needsOnboarding) {
        setPendingScene(false);
        setTurnPhase("idle");
        setDraftSceneText("");
        return;
      }
      const requestSessionId = sessionId;
      const bootstrapKey = `${requestSessionId}:${bootstrapNonce}`;
      if (bootstrappedSceneKeyRef.current === bootstrapKey) {
        return;
      }
      bootstrappedSceneKeyRef.current = bootstrapKey;
      beginTurnOperation({
        notice: "Reading world state and selecting your next storylet...",
        phase: "confirming",
        setPending: setPendingScene,
      });
      try {
        await fetchScene(requestSessionId, vars);
        setTurnPhase("weaving_ahead");
        await refreshPostTurnContext(requestSessionId);
      } catch (error) {
        if (!isStaleSession(requestSessionId)) {
          bootstrappedSceneKeyRef.current = "";
          pushToast("The world did not answer.", String(error));
        }
      } finally {
        if (active && !isStaleSession(requestSessionId)) {
          finishTurnOperation(setPendingScene);
        }
      }
    }
    void bootstrap();
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, needsOnboarding, bootstrapNonce]);

  useEffect(() => {
    if (mode !== "reflect" || history.length > 0) {
      return;
    }
    void refreshMemory(historyLimit);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, history.length]);

  useEffect(() => {
    if (!ENABLE_CONSTELLATION && mode === "constellation") {
      setMode("explore");
    }
  }, [mode]);

  useEffect(() => {
    if (needsOnboarding) {
      return;
    }
    scheduleScenePrefetch();
  }, [choices.length, needsOnboarding, scheduleScenePrefetch, sceneText, sessionId]);

  async function handleFactSearch(query: string) {
    setBackendNotice("Searching the world memory graph for matching facts...");
    setPendingSearch(true);
    try {
      const response = await getWorldFacts(sessionId, query, 8);
      setFacts(response.facts ?? []);
    } catch (error) {
      pushToast("Could not recall matching facts.", String(error));
    } finally {
      setPendingSearch(false);
      setBackendNotice("");
    }
  }

  function handlePreferenceVarUpdate(key: string, value: string | number | boolean) {
    persistVars({
      ...vars,
      [key]: value,
    });
  }

  async function handleLongTurnPromptSubmit() {
    const trimmed = longTurnPromptValue.trim();
    if (!trimmed) {
      return;
    }
    const promptKey =
      longTurnPromptType === "hope"
        ? PROMPT_HOPE_KEY
        : longTurnPromptType === "fear"
          ? PROMPT_FEAR_KEY
          : PROMPT_NOTICE_KEY;
    const patch: VarsRecord = {
      [promptKey]: trimmed,
    };
    applyPromptPatch(patch, `World-weaving prompt: ${longTurnPromptType}`);
    setLongTurnPromptValue("");
    void triggerPrefetch("long-turn-prompt");
  }

  function handleLongTurnVibeApply(vibe: string) {
    setLongTurnVibe(vibe);
    applyPromptPatch({ [PROMPT_VIBE_KEY]: vibe }, "World-weaving lens update");
    void triggerPrefetch("long-turn-vibe");
  }

  async function handleSurpriseSafeAction() {
    if (needsOnboarding) {
      pushToast(
        "Onboarding required first.",
        "Complete setup in Explore mode before using Create surprises.",
      );
      setMode("explore");
      return;
    }

    const nextVars: VarsRecord = {
      ...vars,
      surprise_safe: true,
    };
    persistVars(nextVars);
    setMode("explore");
    await handleAction(SURPRISE_SAFE_ACTION, nextVars);
  }

  async function handleConstellationJump(location: string) {
    beginTurnOperation({
      notice: "Jumping to target location and resolving the next storylet...",
      phase: "confirming",
      setPending: setPendingScene,
    });
    const requestSessionId = sessionId;
    const previousVars = vars;
    try {
      const nextScene = await postNext(requestSessionId, {
        ...toNextPayloadVars(previousVars, false),
        location,
      });
      if (isStaleSession(requestSessionId)) {
        return;
      }
      const nextVars = normalizeVars(nextScene.vars);
      setTurnPhase("rendering");
      setSceneText(nextScene.text);
      setChoices(nextScene.choices ?? []);
      persistVars(nextVars);
      setMode("explore");
      setChanges(
        buildWhatChangedReceipts({
          eventLabel: `Constellation jump: ${location}`,
          previousVars,
          nextVars,
          stateChanges: { location },
        }),
      );
      setTurnPhase("weaving_ahead");
      await refreshPostTurnContext(requestSessionId);
    } catch (error) {
      if (isStaleSession(requestSessionId)) {
        return;
      }
      pushToast("Constellation jump failed.", String(error));
    } finally {
      if (!isStaleSession(requestSessionId)) {
        finishTurnOperation(setPendingScene);
      }
    }
  }

  const sessionLabel = useMemo(() => sessionId.slice(-12), [sessionId]);
  const modeRouterPayload = useMemo<ModeRouterPayload>(() => ({
    explore: {
      needsOnboarding,
      pendingScene,
      backendNotice,
      worldTheme: worldThemeInput,
      playerRole: characterInput,
      noticeFirst: noticeFirstInput,
      oneHope: oneHopeInput,
      oneFear: oneFearInput,
      vibeLens: vibeLensInput,
      onWorldThemeChange: setWorldThemeInput,
      onPlayerRoleChange: setCharacterInput,
      onNoticeFirstChange: setNoticeFirstInput,
      onOneHopeChange: setOneHopeInput,
      onOneFearChange: setOneFearInput,
      onVibeLensChange: setVibeLensInput,
      onOnboardingSubmit: handleOnboardingSubmit,
      history,
      facts,
      pendingSearch,
      onSearchFacts: handleFactSearch,
      sceneText,
      draftSceneText,
      choices,
      anyPending,
      turnPhase,
      onChoose: handleChoice,
      pendingAction,
      onSubmitAction: handleAction,
      onTypingActivity: notifyTypingActivity,
      longTurnPromptType,
      onLongTurnPromptTypeChange: setLongTurnPromptType,
      longTurnPromptValue,
      onLongTurnPromptValueChange: setLongTurnPromptValue,
      onLongTurnPromptSubmit: handleLongTurnPromptSubmit,
      longTurnVibe,
      onLongTurnVibeApply: handleLongTurnVibeApply,
      changes,
      vars,
      availableDirections,
      leads,
      pendingMove,
      onMove: handleMove,
      showCompass: ENABLE_ASSISTIVE_SPATIAL,
      prefetchStatus,
      showPrefetchStatus: SHOW_PREFETCH_STATUS,
    },
    reflect: {
      sessionId,
      varsSnapshot: vars,
      events: history,
      pending: pendingHistory,
      historyLimit,
      onRefreshHistory: refreshMemory,
    },
    create: {
      vars,
      pending: pendingAction,
      pendingNotice: backendNotice,
      blockedByOnboarding: needsOnboarding,
      onSetVar: handlePreferenceVarUpdate,
      onSurpriseSafe: handleSurpriseSafeAction,
    },
    constellation: {
      sessionId,
      onJumpToLocation: handleConstellationJump,
    },
  }), [
    anyPending,
    availableDirections,
    backendNotice,
    changes,
    characterInput,
    choices,
    draftSceneText,
    facts,
    handleAction,
    handleChoice,
    handleConstellationJump,
    handleFactSearch,
    handleLongTurnPromptSubmit,
    handleMove,
    handleOnboardingSubmit,
    handlePreferenceVarUpdate,
    handleSurpriseSafeAction,
    history,
    historyLimit,
    longTurnPromptType,
    longTurnPromptValue,
    longTurnVibe,
    needsOnboarding,
    noticeFirstInput,
    notifyTypingActivity,
    oneFearInput,
    oneHopeInput,
    pendingAction,
    pendingHistory,
    pendingMove,
    pendingScene,
    pendingSearch,
    prefetchStatus,
    sceneText,
    sessionId,
    turnPhase,
    vars,
    vibeLensInput,
    worldThemeInput,
  ]);

  return (
    <div className="app-shell">
      <AppTopbar
        mode={mode}
        onModeChange={setMode}
        enableConstellation={ENABLE_CONSTELLATION}
        onOpenSettings={() => setIsSettingsOpen(true)}
        sessionLabel={sessionLabel}
        anyBusy={anyBusy}
        runtimeStatus={topbarRuntimeStatus}
        onResetSession={handleResetSession}
        pendingScene={pendingScene}
        enableDevReset={ENABLE_DEV_RESET}
        onDevHardReset={handleDevHardReset}
      />

      <ModeRouter mode={mode} payload={modeRouterPayload} />

      <ErrorToastStack toasts={toasts} onDismiss={dismissToast} />
      <SettingsDrawer
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onModelChanged={() => {
          void refreshReadiness();
        }}
      />

      {settingsReadiness && !settingsReadiness.ready && (
        <SetupModal
          missing={settingsReadiness.missing}
          onComplete={() => {
            void refreshReadiness();
          }}
        />
      )}
    </div>
  );
}
