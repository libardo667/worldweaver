import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";

import {
  getAvailableModels,
  getCurrentModel,
  getSpatialNavigation,
  getStateSummary,
  getWorldFacts,
  getWorldHistory,
  postAction,
  postDevHardReset,
  postNext,
  putCurrentModel,
  postResetSession,
  postSessionBootstrap,
  postSpatialMove,
  streamAction,
} from "./api/wwClient";
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
  CurrentModelResponse,
  ModelSummary,
  TurnPhase,
  ToastItem,
  VarsRecord,
  WorldEvent,
} from "./types";

type ClientMode = "explore" | "reflect" | "create" | "constellation";
const WORLD_THEME_KEY = "world_theme";
const PLAYER_ROLE_KEY = "player_role";
const CHARACTER_PROFILE_KEY = "character_profile";
const SURPRISE_SAFE_ACTION = "Surprise me with a safe but intriguing turn that fits this world.";
const PREFERENCE_PREFIXES = ["pref.", "lens."];
const PREFERENCE_KEYS = new Set(["surprise_safe"]);
const PROMPT_NOTICE_KEY = "pref.notice_first";
const PROMPT_HOPE_KEY = "pref.one_hope";
const PROMPT_FEAR_KEY = "pref.one_fear";
const PROMPT_VIBE_KEY = "lens.vibe";
const BLOCKED_MOVE_DETAIL = "Cannot move in that direction";
const ENABLE_CONSTELLATION = (() => {
  const raw = String(import.meta.env.VITE_WW_ENABLE_CONSTELLATION ?? "").trim().toLowerCase();
  return raw === "1" || raw === "true" || raw === "yes";
})();
const ENABLE_DEV_RESET = (() => {
  const raw = String(import.meta.env.VITE_WW_ENABLE_DEV_RESET ?? "").trim().toLowerCase();
  if (raw.length === 0) {
    return Boolean(import.meta.env.DEV);
  }
  return raw === "1" || raw === "true" || raw === "yes";
})();
const SHOW_PREFETCH_STATUS = (() => {
  const raw = String(import.meta.env.VITE_WW_SHOW_PREFETCH_STATUS ?? "1").trim().toLowerCase();
  return raw === "1" || raw === "true" || raw === "yes";
})();

const DERIVED_VARS = new Set([
  "inventory_count",
  "total_item_quantity",
  "relationship_count",
  "time_of_day",
  "weather",
  "danger_level",
  "inventory_items",
  "known_people",
  "goal_primary",
  "goal_subgoals",
  "goal_urgency",
  "goal_complication",
]);

function normalizeVars(value: unknown): VarsRecord {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as VarsRecord;
}

function makeId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function toNextPayloadVars(vars: VarsRecord, omitLocation = false): VarsRecord {
  const out: VarsRecord = {};
  for (const [key, value] of Object.entries(vars)) {
    if (key.startsWith("_")) {
      continue;
    }
    if (DERIVED_VARS.has(key)) {
      continue;
    }
    if (key.startsWith("_mood_")) {
      continue;
    }
    if (omitLocation && key === "location") {
      continue;
    }
    out[key] = value;
  }
  return out;
}

function applyLocalSet(baseVars: VarsRecord, setPayload: VarsRecord): VarsRecord {
  const next: VarsRecord = { ...baseVars };
  for (const [key, value] of Object.entries(setPayload)) {
    if (
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      ("inc" in value || "dec" in value)
    ) {
      const current = typeof next[key] === "number" ? (next[key] as number) : 0;
      const inc = Number((value as { inc?: unknown }).inc ?? 0);
      const dec = Number((value as { dec?: unknown }).dec ?? 0);
      next[key] = current + inc - dec;
    } else {
      next[key] = value;
    }
  }
  return next;
}

function readStringVar(vars: VarsRecord, key: string): string {
  const raw = vars[key];
  if (typeof raw !== "string") {
    return "";
  }
  return raw.trim();
}

function formatUsd(value: number): string {
  const amount = Number.isFinite(value) ? value : 0;
  if (amount === 0) {
    return "$0.00";
  }
  if (amount < 0.01) {
    return `$${amount.toFixed(4)}`;
  }
  return `$${amount.toFixed(2)}`;
}

function isPreferenceVar(key: string): boolean {
  return PREFERENCE_KEYS.has(key) || PREFERENCE_PREFIXES.some((prefix) => key.startsWith(prefix));
}

function getErrorDetail(error: unknown): string {
  if (error instanceof Error) {
    const message = error.message.trim();
    if (!message) {
      return "Unknown error";
    }
    try {
      const parsed = JSON.parse(message) as { detail?: unknown };
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        return parsed.detail.trim();
      }
    } catch {
      // non-JSON error bodies are already safe to render directly
    }
    return message;
  }
  const detail = String(error ?? "").trim();
  return detail || "Unknown error";
}

function extractPreferenceVars(vars: VarsRecord): VarsRecord {
  const out: VarsRecord = {};
  for (const [key, value] of Object.entries(vars)) {
    if (isPreferenceVar(key)) {
      out[key] = value;
    }
  }
  return out;
}

function mergePreferenceVars(serverVars: VarsRecord, localVars: VarsRecord): VarsRecord {
  return {
    ...serverVars,
    ...extractPreferenceVars(localVars),
  };
}

function buildPromptVars({
  noticeFirst,
  oneHope,
  oneFear,
  vibeLens,
}: {
  noticeFirst: string;
  oneHope: string;
  oneFear: string;
  vibeLens: string;
}): VarsRecord {
  const out: VarsRecord = {};
  if (noticeFirst.trim()) {
    out[PROMPT_NOTICE_KEY] = noticeFirst.trim();
  }
  if (oneHope.trim()) {
    out[PROMPT_HOPE_KEY] = oneHope.trim();
  }
  if (oneFear.trim()) {
    out[PROMPT_FEAR_KEY] = oneFear.trim();
  }
  if (vibeLens.trim()) {
    out[PROMPT_VIBE_KEY] = vibeLens.trim();
  }
  return out;
}

export default function App() {
  const [mode, setMode] = useState<ClientMode>("explore");
  const [sessionId, setSessionId] = useState<string>(() => getOrCreateSessionId());
  const [vars, setVars] = useState<VarsRecord>(() => loadSessionVars());
  const [sceneText, setSceneText] = useState<string>("Weaving the world around you...");
  const [draftSceneText, setDraftSceneText] = useState<string>("");
  const [choices, setChoices] = useState<Choice[]>([]);
  const [directions, setDirections] = useState<string[]>([]);
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
  const [availableModels, setAvailableModels] = useState<ModelSummary[]>([]);
  const [currentModel, setCurrentModel] = useState<CurrentModelResponse | null>(null);
  const [pendingModelSwitch, setPendingModelSwitch] = useState(false);
  const [needsOnboarding, setNeedsOnboarding] = useState<boolean>(
    () => getOnboardedSessionId() !== sessionId,
  );
  const [bootstrapNonce, setBootstrapNonce] = useState(0);
  const latestSessionId = useRef(sessionId);
  const actionStreamAbortRef = useRef<AbortController | null>(null);
  const bootstrappedSceneKeyRef = useRef("");

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

  const refreshModelSettings = useCallback(async () => {
    try {
      const [models, activeModel] = await Promise.all([
        getAvailableModels(),
        getCurrentModel(),
      ]);
      setAvailableModels(models ?? []);
      setCurrentModel(activeModel);
    } catch (error) {
      pushToast("Could not load model settings.", String(error), "info");
    }
  }, [pushToast]);

  const modelSelectOptions = useMemo(() => {
    const options = (availableModels ?? []).map((model) => ({
      model_id: model.model_id,
      label: model.label,
      tier: model.tier,
      estimated_10_turn_cost_usd: model.estimated_10_turn_cost_usd,
    }));
    if (!currentModel) {
      return options;
    }
    if (!options.some((option) => option.model_id === currentModel.model_id)) {
      options.unshift({
        model_id: currentModel.model_id,
        label: currentModel.label,
        tier: currentModel.tier,
        estimated_10_turn_cost_usd:
          Number(currentModel.estimated_session_cost?.total_cost_usd ?? 0),
      });
    }
    return options;
  }, [availableModels, currentModel]);

  async function handleModelSelection(event: ChangeEvent<HTMLSelectElement>) {
    const nextModelId = event.target.value.trim();
    if (!nextModelId || pendingModelSwitch || nextModelId === currentModel?.model_id) {
      return;
    }
    setPendingModelSwitch(true);
    try {
      const switched = await putCurrentModel(nextModelId);
      const refreshed = await getCurrentModel();
      setCurrentModel(refreshed);
      pushToast(
        "Model switched.",
        `${switched.label} selected (${formatUsd(switched.estimated_10_turn_cost_usd)} / 10 turns).`,
        "info",
      );
    } catch (error) {
      pushToast("Model switch failed.", String(error));
      await refreshModelSettings();
    } finally {
      setPendingModelSwitch(false);
    }
  }

  useEffect(() => {
    void refreshModelSettings();
  }, [refreshModelSettings]);

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

  async function refreshPlace(requestSessionId = sessionId) {
    try {
      const spatial = await getSpatialNavigation(requestSessionId);
      if (isStaleSession(requestSessionId)) {
        return;
      }
      setDirections(spatial.directions ?? []);
      setLeads(spatial.leads ?? []);
    } catch (error) {
      if (isStaleSession(requestSessionId)) {
        return;
      }
      pushToast("Could not read nearby paths.", String(error));
    }
  }

  async function refreshPostTurnContext(requestSessionId = sessionId) {
    await refreshMemory(historyLimit, requestSessionId);
    void refreshPlace(requestSessionId);
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
      const predicted = applyLocalSet(previousVars, normalizeVars(choice.set));
      const scene = await postNext(requestSessionId, toNextPayloadVars(predicted));
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
      setTurnPhase("weaving_ahead");
      await refreshPostTurnContext(requestSessionId);
    } catch (error) {
      if (isStaleSession(requestSessionId)) {
        return;
      }
      const detail = getErrorDetail(error);
      if (detail === BLOCKED_MOVE_DETAIL) {
        pushToast(
          "Movement blocked.",
          "That route is currently impassable. Try a different direction.",
          "info",
        );
        void refreshPlace(requestSessionId);
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
      setDirections([]);
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
      setDirections([]);
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
          <div className="model-control">
            <label htmlFor="model-select">Model</label>
            <select
              id="model-select"
              value={currentModel?.model_id ?? ""}
              onChange={handleModelSelection}
              disabled={anyBusy || pendingModelSwitch || !currentModel || modelSelectOptions.length === 0}
            >
              {!currentModel ? <option value="">Loading models...</option> : null}
              {modelSelectOptions.map((option) => (
                <option key={option.model_id} value={option.model_id}>
                  {option.label} ({option.tier}) - {formatUsd(option.estimated_10_turn_cost_usd)}
                </option>
              ))}
            </select>
            <span className={`model-cost ${pendingModelSwitch ? "active" : ""}`}>
              {pendingModelSwitch
                ? "Applying model..."
                : currentModel
                  ? `${formatUsd(
                      Number(currentModel.estimated_session_cost?.total_cost_usd ?? 0),
                    )} estimated / ${currentModel.estimated_session_cost?.turns ?? 10} turns`
                  : "Model cost unavailable"}
            </span>
          </div>
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
                directions={directions}
                leads={leads}
                pendingMove={pendingMove}
                onMove={handleMove}
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
    </div>
  );
}
