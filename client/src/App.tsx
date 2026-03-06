import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getSettingsReadiness,
  getSpatialNavigation,
  getStateSummary,
  getWorldFacts,
  getWorldHistory,
  postAction,
  postDevHardReset,
  postNext,
  postResetSession,
  postSessionBootstrap,
  postSpatialMove,
  streamAction,
} from "./api/wwClient";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { SetupModal } from "./components/SetupModal";
import { ErrorToastStack } from "./components/ErrorToastStack";
import { FreeformInput } from "./components/FreeformInput";
import { MemoryPanel } from "./components/MemoryPanel";
import { NowPanel } from "./components/NowPanel";
import { PlacePanel } from "./components/PlacePanel";
import { SetupOnboarding } from "./components/SetupOnboarding";
import { WhatChangedStrip } from "./components/WhatChangedStrip";
import { usePrefetchFrontier } from "./hooks/usePrefetchFrontier";
import { AppShell } from "./layout/AppShell";
import { buildWhatChangedReceipts } from "./utils/diffVars";
import { ConstellationView } from "./views/ConstellationView";
import { CreateView } from "./views/CreateView";
import { ReflectView } from "./views/ReflectView";
import {
  BLOCKED_MOVE_DETAIL,
  BLOCKED_MOVE_TOAST_COOLDOWN_MS,
  buildChoiceTakenDelta,
  buildPromptVars,
  CHARACTER_PROFILE_KEY,
  ENABLE_ASSISTIVE_SPATIAL,
  ENABLE_CONSTELLATION,
  ENABLE_DEV_RESET,
  extractPreferenceVars,
  getErrorDetail,
  makeId,
  mergePreferenceVars,
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
  clearSessionStorage,
  getOnboardedSessionId,
  getOrCreateSessionId,
  loadSessionVars,
  replaceSessionId,
  saveSessionVars,
  setOnboardedSessionId,
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

  function clearWorldweaverLocalStoragePrefix(): void {
    const keys: string[] = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i);
      if (key && key.startsWith("ww.")) {
        keys.push(key);
      }
    }
    for (const key of keys) {
      localStorage.removeItem(key);
    }
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

  async function refreshPostTurnContext(requestSessionId = sessionId) {
    await refreshMemory(historyLimit, requestSessionId);
    if (ENABLE_ASSISTIVE_SPATIAL) {
      scheduleBestEffortPlaceRefresh(requestSessionId);
    }
  }

  async function fetchScene(
    requestSessionId: string,
    initialVars: VarsRecord,
    omitLocation = false,
  ) {
    const scene = await postNext(
      requestSessionId,
      toNextPayloadVars(initialVars, omitLocation),
    );
    if (isStaleSession(requestSessionId)) {
      return;
    }
    setSceneText(scene.text);
    setChoices(scene.choices ?? []);
    persistVars(mergePreferenceVars(normalizeVars(scene.vars), initialVars));
  }

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
      setBackendNotice("Reading world state and selecting your next storylet...");
      setPendingScene(true);
      setTurnPhase("confirming");
      setDraftSceneText("");
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
          setPendingScene(false);
          setTurnPhase("idle");
          setDraftSceneText("");
          setBackendNotice("");
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

  async function handleChoice(choice: Choice) {
    setBackendNotice("Applying your choice and weaving the next storylet...");
    setPendingScene(true);
    setTurnPhase("confirming");
    setDraftSceneText("");
    const requestSessionId = sessionId;
    const previousVars = vars;
    try {
      const intentDelta = buildChoiceTakenDelta(normalizeVars(choice.set));
      const scene = await postNext(requestSessionId, toNextPayloadVars(previousVars), intentDelta);
      if (isStaleSession(requestSessionId)) {
        return;
      }
      const nextVars = mergePreferenceVars(normalizeVars(scene.vars), previousVars);

      setTurnPhase("rendering");
      setSceneText(scene.text);
      setChoices(scene.choices ?? []);
      persistVars(nextVars);

      setChanges(
        buildWhatChangedReceipts({
          eventLabel: `Choice: ${choice.label}`,
          previousVars,
          nextVars,
          choiceSet: normalizeVars(choice.set),
        }),
      );
      setTurnPhase("weaving_ahead");
      await refreshPostTurnContext(requestSessionId);
    } catch (error) {
      if (isStaleSession(requestSessionId)) {
        return;
      }
      pushToast("Choice failed to resolve.", String(error));
    } finally {
      if (!isStaleSession(requestSessionId)) {
        setPendingScene(false);
        setTurnPhase("idle");
        setDraftSceneText("");
        setBackendNotice("");
      }
    }
  }

  async function handleAction(actionText: string, inputVars?: VarsRecord) {
    setBackendNotice("Interpreting your action and resolving world consequences...");
    setPendingAction(true);
    setTurnPhase("interpreting");
    setDraftSceneText("");
    const requestSessionId = sessionId;
    const previousVars = inputVars ?? vars;
    const actionPreferenceVars = extractPreferenceVars(previousVars);
    actionStreamAbortRef.current?.abort();
    const controller = new AbortController();
    actionStreamAbortRef.current = controller;
    try {
      let result;
      let receivedDraft = false;
      try {
        result = await streamAction(
          requestSessionId,
          actionText,
          actionPreferenceVars,
          (draftText) => {
            receivedDraft = true;
            if (!isStaleSession(requestSessionId)) {
              setTurnPhase("rendering");
              setDraftSceneText(draftText);
            }
          },
          controller.signal,
        );
      } catch (streamError) {
        if (controller.signal.aborted) {
          return;
        }
        if (!receivedDraft) {
          setTurnPhase("confirming");
          result = await postAction(requestSessionId, actionText, actionPreferenceVars);
        } else {
          throw streamError;
        }
      }
      if (isStaleSession(requestSessionId)) {
        return;
      }
      const nextVars = mergePreferenceVars(normalizeVars(result.vars), previousVars);

      setTurnPhase("rendering");
      setSceneText(
        result.triggered_storylet
          ? `${result.narrative}\n\n${result.triggered_storylet}`
          : result.narrative,
      );
      setDraftSceneText("");
      setChoices(result.choices ?? []);
      persistVars(nextVars);

      setChanges(
        buildWhatChangedReceipts({
          eventLabel: `Action: ${actionText}`,
          previousVars,
          nextVars,
          stateChanges: normalizeVars(result.state_changes),
        }),
      );
      setTurnPhase("weaving_ahead");
      await refreshPostTurnContext(requestSessionId);
    } catch (error) {
      if (isStaleSession(requestSessionId)) {
        return;
      }
      pushToast("Your action lost coherence.", String(error));
    } finally {
      if (actionStreamAbortRef.current === controller) {
        actionStreamAbortRef.current = null;
      }
      if (!isStaleSession(requestSessionId)) {
        setPendingAction(false);
        setTurnPhase("idle");
        setDraftSceneText("");
        setBackendNotice("");
      }
    }
  }

  async function handleMove(direction: string) {
    setBackendNotice("Validating movement and fetching the destination storylet...");
    setPendingMove(true);
    setTurnPhase("confirming");
    setDraftSceneText("");
    const requestSessionId = sessionId;
    const previousVars = vars;
    try {
      const movement = await postSpatialMove(requestSessionId, direction);
      const summary = await getStateSummary(requestSessionId);
      if (isStaleSession(requestSessionId)) {
        return;
      }
      const serverVars = normalizeVars(summary.variables);
      const mergedRequestVars = mergePreferenceVars(serverVars, previousVars);
      const nextScene = await postNext(
        requestSessionId,
        toNextPayloadVars(mergedRequestVars, false),
      );
      if (isStaleSession(requestSessionId)) {
        return;
      }
      const nextVars = mergePreferenceVars(normalizeVars(nextScene.vars), previousVars);

      setTurnPhase("rendering");
      setSceneText(nextScene.text);
      setChoices(nextScene.choices ?? []);
      persistVars(nextVars);
      setChanges(
        buildWhatChangedReceipts({
          eventLabel: movement.result,
          previousVars,
          nextVars,
        }),
      );
      lastBlockedMoveToastAtRef.current = 0;
      setTurnPhase("weaving_ahead");
      await refreshPostTurnContext(requestSessionId);
    } catch (error) {
      if (isStaleSession(requestSessionId)) {
        return;
      }
      const detail = getErrorDetail(error);
      if (detail === BLOCKED_MOVE_DETAIL) {
        const now = Date.now();
        if (now - lastBlockedMoveToastAtRef.current >= BLOCKED_MOVE_TOAST_COOLDOWN_MS) {
          lastBlockedMoveToastAtRef.current = now;
          pushToast(
            "Movement blocked.",
            "That route is currently impassable. Try a different direction.",
            "info",
          );
        }
        scheduleBestEffortPlaceRefresh(requestSessionId);
        return;
      }
      pushToast("Movement failed.", detail);
    } finally {
      if (!isStaleSession(requestSessionId)) {
        setPendingMove(false);
        setTurnPhase("idle");
        setDraftSceneText("");
        setBackendNotice("");
      }
    }
  }

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

  async function handleResetSession() {
    setBackendNotice("Resetting world state and clearing session context...");
    setPendingScene(true);
    setTurnPhase("confirming");
    setDraftSceneText("");
    try {
      actionStreamAbortRef.current?.abort();
      actionStreamAbortRef.current = null;
      bootstrappedSceneKeyRef.current = "";
      const resetResult = await postResetSession();
      clearSessionStorage();
      const replacement = replaceSessionId();
      latestSessionId.current = replacement;
      setMode("explore");
      setSessionId(replacement);
      setSceneText("A new thread begins.");
      setChoices([]);
      setHistory([]);
      setFacts([]);
      setAvailableDirections({});
      setLeads([]);
      setHistoryLimit(60);
      setChanges([{ id: makeId("evt"), text: "Session reset and rethreaded." }]);
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
      pushToast(
        "Session reset.",
        resetResult.legacy_seed_mode
          ? `World cleared. Legacy seed mode inserted ${resetResult.storylets_seeded} storylets.`
          : "World cleared. Onboarding is required before the first scene.",
        "info",
      );
    } catch (error) {
      pushToast("Session reset failed.", String(error));
    } finally {
      setPendingScene(false);
      setTurnPhase("idle");
      setDraftSceneText("");
      setBackendNotice("");
    }
  }

  async function handleDevHardReset() {
    if (!window.confirm("Hard reset will wipe all world data and clear local WorldWeaver storage. Continue?")) {
      return;
    }

    setBackendNotice("Running developer hard reset and rebuilding a clean thread...");
    setPendingScene(true);
    setTurnPhase("confirming");
    setDraftSceneText("");
    try {
      actionStreamAbortRef.current?.abort();
      actionStreamAbortRef.current = null;
      bootstrappedSceneKeyRef.current = "";
      const resetResult = await postDevHardReset();
      clearSessionStorage();
      clearWorldweaverLocalStoragePrefix();
      const replacement = replaceSessionId();
      latestSessionId.current = replacement;
      setMode("explore");
      setSessionId(replacement);
      setSceneText("Development hard reset complete.");
      setChoices([]);
      setHistory([]);
      setFacts([]);
      setAvailableDirections({});
      setLeads([]);
      setHistoryLimit(60);
      setChanges([{ id: makeId("evt"), text: "Developer hard reset wiped backend world + local state." }]);
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
      await refreshReadiness();
      pushToast("Dev hard reset complete.", resetResult.message, "info");
    } catch (error) {
      pushToast("Dev hard reset failed.", String(error));
    } finally {
      setPendingScene(false);
      setTurnPhase("idle");
      setDraftSceneText("");
      setBackendNotice("");
    }
  }

  async function handleConstellationJump(location: string) {
    setBackendNotice("Jumping to target location and resolving the next storylet...");
    setPendingScene(true);
    setTurnPhase("confirming");
    setDraftSceneText("");
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
        setPendingScene(false);
        setTurnPhase("idle");
        setDraftSceneText("");
        setBackendNotice("");
      }
    }
  }

  async function handleOnboardingSubmit() {
    const theme = worldThemeInput.trim();
    const character = characterInput.trim();
    if (!theme || !character) {
      pushToast(
        "Setup incomplete.",
        "Please answer both onboarding questions before starting.",
      );
      return;
    }
    const requestSessionId = sessionId;
    setBackendNotice("Generating your world and preparing the opening storylets...");
    setPendingScene(true);
    setTurnPhase("confirming");
    setDraftSceneText("");
    try {
      const bootstrap = await postSessionBootstrap(requestSessionId, {
        world_theme: theme,
        player_role: character,
        description: `A player-authored world focused on ${theme}.`,
        bootstrap_source: "onboarding",
      });
      if (isStaleSession(requestSessionId)) {
        return;
      }

      const promptVars = buildPromptVars({
        noticeFirst: noticeFirstInput,
        oneHope: oneHopeInput,
        oneFear: oneFearInput,
        vibeLens: vibeLensInput,
      });
      const seededVars: VarsRecord = {
        ...normalizeVars(bootstrap.vars),
        ...extractPreferenceVars(vars),
        ...promptVars,
        [WORLD_THEME_KEY]: theme,
        [PLAYER_ROLE_KEY]: character,
        [CHARACTER_PROFILE_KEY]: character,
      };
      persistVars(seededVars);
      setLongTurnVibe(vibeLensInput.trim());
      setOnboardedSessionId(requestSessionId);
      setNeedsOnboarding(false);
      setSceneText("Weaving your world setup into the first scene...");
      setTurnPhase("weaving_ahead");
      setChanges([
        {
          id: makeId("evt"),
          text: `World setup: ${theme} | Character: ${character}`,
        },
      ]);
      setBootstrapNonce((value) => value + 1);
      void triggerPrefetch("onboarding-prompts");
      pushToast(
        "Setup captured.",
        `Generated ${bootstrap.storylets_created} opening storylets for this world.`,
        "info",
      );
    } catch (error) {
      if (isStaleSession(requestSessionId)) {
        return;
      }
      pushToast("World bootstrap failed.", String(error));
    } finally {
      if (!isStaleSession(requestSessionId)) {
        setPendingScene(false);
        setTurnPhase("idle");
        setDraftSceneText("");
        setBackendNotice("");
      }
    }
  }

  const sessionLabel = useMemo(() => sessionId.slice(-12), [sessionId]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <h1>WorldWeaver Explorer</h1>
          <p>
            {mode === "reflect"
              ? "Reflect mode chronicle view"
              : mode === "create"
                ? "Create mode preference and lens controls"
                : mode === "constellation"
                  ? "Semantic constellation debug view"
                  : "API-first Explore mode v1"}
          </p>
        </div>
        <div className="topbar-meta">
          <div className="mode-toggle" role="tablist" aria-label="Client mode">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "explore"}
              className={`text-btn mode-toggle-btn ${mode === "explore" ? "active" : ""}`}
              onClick={() => setMode("explore")}
            >
              Explore
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "reflect"}
              className={`text-btn mode-toggle-btn ${mode === "reflect" ? "active" : ""}`}
              onClick={() => setMode("reflect")}
            >
              Reflect
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "create"}
              className={`text-btn mode-toggle-btn ${mode === "create" ? "active" : ""}`}
              onClick={() => setMode("create")}
            >
              Create
            </button>
            {ENABLE_CONSTELLATION ? (
              <button
                type="button"
                role="tab"
                aria-selected={mode === "constellation"}
                className={`text-btn mode-toggle-btn ${mode === "constellation" ? "active" : ""}`}
                onClick={() => setMode("constellation")}
              >
                Constellation
              </button>
            ) : null}
          </div>
          <button
            type="button"
            className="settings-toggle-btn"
            onClick={() => setIsSettingsOpen(true)}
            aria-label="Open settings"
            title="Model and API Settings"
          >
            ⚙
          </button>
          <span>Session ...{sessionLabel}</span>
          <span className={`backend-status ${anyBusy ? "active" : ""}`}>
            {anyBusy && backendNotice ? backendNotice : "Backend ready"}
          </span>
          <button
            type="button"
            className="danger-btn"
            onClick={handleResetSession}
            disabled={anyBusy}
            data-loading={pendingScene ? "true" : "false"}
          >
            Reset session
          </button>
          {ENABLE_DEV_RESET ? (
            <button
              type="button"
              className="danger-btn"
              onClick={handleDevHardReset}
              disabled={anyBusy}
              data-loading={pendingScene ? "true" : "false"}
            >
              Dev hard reset
            </button>
          ) : null}
        </div>
      </header>

      {mode === "explore" ? (
        needsOnboarding ? (
          <SetupOnboarding
            pending={pendingScene}
            pendingNotice={backendNotice}
            worldTheme={worldThemeInput}
            playerRole={characterInput}
            noticeFirst={noticeFirstInput}
            oneHope={oneHopeInput}
            oneFear={oneFearInput}
            vibeLens={vibeLensInput}
            onWorldThemeChange={setWorldThemeInput}
            onPlayerRoleChange={setCharacterInput}
            onNoticeFirstChange={setNoticeFirstInput}
            onOneHopeChange={setOneHopeInput}
            onOneFearChange={setOneFearInput}
            onVibeLensChange={setVibeLensInput}
            onSubmit={handleOnboardingSubmit}
          />
        ) : (
          <AppShell
            memoryPanel={
              <MemoryPanel
                events={history}
                facts={facts}
                searchPending={pendingSearch}
                onSearch={handleFactSearch}
              />
            }
            nowPanel={
              <section className="center-column">
                <NowPanel
                  text={sceneText}
                  draftText={draftSceneText}
                  choices={choices}
                  pending={anyPending}
                  phase={turnPhase}
                  backendNotice={backendNotice}
                  onChoose={handleChoice}
                />
                <FreeformInput
                  pending={pendingAction}
                  onSubmit={handleAction}
                  onTypingActivity={notifyTypingActivity}
                />
                {anyPending ? (
                  <section className="panel weaving-prompts-inline">
                    <header className="panel-header">
                      <h3>World-Weaving Prompts</h3>
                      <span className="panel-meta">Optional, non-blocking</span>
                    </header>
                    <p className="muted">
                      Keep shaping tone while this turn resolves.
                    </p>
                    <div className="weaving-inline-row">
                      <select
                        aria-label="Prompt type"
                        value={longTurnPromptType}
                        onChange={(event) => {
                          const next = event.target.value as "notice" | "hope" | "fear";
                          setLongTurnPromptType(next);
                        }}
                      >
                        <option value="notice">What do you notice first?</option>
                        <option value="hope">Name one hope</option>
                        <option value="fear">Name one fear</option>
                      </select>
                      <input
                        type="text"
                        value={longTurnPromptValue}
                        maxLength={160}
                        placeholder="Optional prompt answer"
                        onChange={(event) => setLongTurnPromptValue(event.target.value)}
                      />
                      <button
                        type="button"
                        className="text-btn"
                        onClick={handleLongTurnPromptSubmit}
                        disabled={!longTurnPromptValue.trim()}
                      >
                        Save prompt
                      </button>
                    </div>
                    <div className="weaving-vibe-row">
                      <span className="panel-meta">Vibe lens</span>
                      {(["cozy", "tense", "uncanny", "hopeful"] as const).map((lens) => (
                        <button
                          key={lens}
                          type="button"
                          className={`text-btn ${longTurnVibe === lens ? "active-lens" : ""}`}
                          onClick={() => handleLongTurnVibeApply(lens)}
                        >
                          {lens}
                        </button>
                      ))}
                    </div>
                  </section>
                ) : null}
                <WhatChangedStrip changes={changes} pending={anyPending} phase={turnPhase} />
              </section>
            }
            placePanel={
              <PlacePanel
                vars={vars}
                availableDirections={availableDirections}
                leads={leads}
                pendingMove={pendingMove}
                onMove={handleMove}
                showCompass={ENABLE_ASSISTIVE_SPATIAL}
                prefetchStatus={prefetchStatus}
                showPrefetchStatus={SHOW_PREFETCH_STATUS}
              />
            }
          />
        )
      ) : mode === "reflect" ? (
        <ReflectView
          sessionId={sessionId}
          varsSnapshot={vars}
          events={history}
          pending={pendingHistory}
          historyLimit={historyLimit}
          onRefreshHistory={refreshMemory}
        />
      ) : mode === "create" ? (
        <CreateView
          vars={vars}
          pending={pendingAction}
          pendingNotice={backendNotice}
          blockedByOnboarding={needsOnboarding}
          onSetVar={handlePreferenceVarUpdate}
          onSurpriseSafe={handleSurpriseSafeAction}
        />
      ) : (
        <ConstellationView
          sessionId={sessionId}
          onJumpToLocation={handleConstellationJump}
        />
      )}

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
