import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";

import {
  getSpatialNavigation,
  getStateSummary,
  getWorldFacts,
  getWorldHistory,
  postAction,
  postNext,
  postResetSession,
  postSpatialMove,
} from "./api/wwClient";
import { ErrorToastStack } from "./components/ErrorToastStack";
import { FreeformInput } from "./components/FreeformInput";
import { MemoryPanel } from "./components/MemoryPanel";
import { NowPanel } from "./components/NowPanel";
import { PlacePanel } from "./components/PlacePanel";
import { WhatChangedStrip } from "./components/WhatChangedStrip";
import { AppShell } from "./layout/AppShell";
import { buildWhatChangedReceipts } from "./utils/diffVars";
import { ReflectView } from "./views/ReflectView";
import {
  clearSessionStorage,
  getOrCreateSessionId,
  loadSessionVars,
  replaceSessionId,
  saveSessionVars,
} from "./state/sessionStore";
import type {
  ChangeItem,
  Choice,
  ToastItem,
  VarsRecord,
  WorldEvent,
} from "./types";

type ClientMode = "explore" | "reflect";
const WORLD_THEME_KEY = "world_theme";
const PLAYER_ROLE_KEY = "player_role";
const CHARACTER_PROFILE_KEY = "character_profile";

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

function hasOnboardingProfile(vars: VarsRecord): boolean {
  return (
    readStringVar(vars, WORLD_THEME_KEY).length > 0
    && readStringVar(vars, PLAYER_ROLE_KEY).length > 0
  );
}


export default function App() {
  const [mode, setMode] = useState<ClientMode>("explore");
  const [sessionId, setSessionId] = useState<string>(() => getOrCreateSessionId());
  const [vars, setVars] = useState<VarsRecord>(() => loadSessionVars());
  const [sceneText, setSceneText] = useState<string>("Weaving the world around you...");
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
  const [historyLimit, setHistoryLimit] = useState(60);
  const [worldThemeInput, setWorldThemeInput] = useState<string>(() => readStringVar(vars, WORLD_THEME_KEY));
  const [characterInput, setCharacterInput] = useState<string>(() => readStringVar(vars, PLAYER_ROLE_KEY));
  const [needsOnboarding, setNeedsOnboarding] = useState<boolean>(() => !hasOnboardingProfile(vars));
  const [bootstrapNonce, setBootstrapNonce] = useState(0);
  const latestSessionId = useRef(sessionId);

  const anyPending = pendingScene || pendingAction || pendingMove;

  useEffect(() => {
    if (hasOnboardingProfile(vars)) {
      setNeedsOnboarding(false);
    }
  }, [vars]);

  useEffect(() => {
    latestSessionId.current = sessionId;
  }, [sessionId]);

  function isStaleSession(requestSessionId: string): boolean {
    return latestSessionId.current !== requestSessionId;
  }

  function pushToast(title: string, detail?: string, kind: ToastItem["kind"] = "error") {
    const toast: ToastItem = { id: makeId("toast"), title, detail, kind };
    setToasts((prev) => [toast, ...prev].slice(0, 4));
  }

  function dismissToast(id: string) {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  }

  function persistVars(nextVars: VarsRecord) {
    setVars(nextVars);
    saveSessionVars(nextVars);
  }

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
    persistVars(normalizeVars(scene.vars));
  }

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      if (needsOnboarding) {
        setPendingScene(false);
        return;
      }
      setPendingScene(true);
      const requestSessionId = sessionId;
      try {
        await fetchScene(requestSessionId, vars);
        await Promise.all([
          refreshMemory(historyLimit, requestSessionId),
          refreshPlace(requestSessionId),
        ]);
      } catch (error) {
        if (!isStaleSession(requestSessionId)) {
          pushToast("The world did not answer.", String(error));
        }
      } finally {
        if (active && !isStaleSession(requestSessionId)) {
          setPendingScene(false);
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

  async function handleChoice(choice: Choice) {
    setPendingScene(true);
    const requestSessionId = sessionId;
    const previousVars = vars;
    try {
      const predicted = applyLocalSet(previousVars, normalizeVars(choice.set));
      const scene = await postNext(requestSessionId, toNextPayloadVars(predicted));
      if (isStaleSession(requestSessionId)) {
        return;
      }
      const nextVars = normalizeVars(scene.vars);

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
      await Promise.all([
        refreshMemory(historyLimit, requestSessionId),
        refreshPlace(requestSessionId),
      ]);
    } catch (error) {
      if (isStaleSession(requestSessionId)) {
        return;
      }
      pushToast("Choice failed to resolve.", String(error));
    } finally {
      if (!isStaleSession(requestSessionId)) {
        setPendingScene(false);
      }
    }
  }

  async function handleAction(actionText: string) {
    setPendingAction(true);
    const requestSessionId = sessionId;
    const previousVars = vars;
    try {
      const result = await postAction(requestSessionId, actionText);
      if (isStaleSession(requestSessionId)) {
        return;
      }
      const nextVars = normalizeVars(result.vars);

      setSceneText(
        result.triggered_storylet
          ? `${result.narrative}\n\n${result.triggered_storylet}`
          : result.narrative,
      );
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
      await Promise.all([
        refreshMemory(historyLimit, requestSessionId),
        refreshPlace(requestSessionId),
      ]);
    } catch (error) {
      if (isStaleSession(requestSessionId)) {
        return;
      }
      pushToast("Your action lost coherence.", String(error));
    } finally {
      if (!isStaleSession(requestSessionId)) {
        setPendingAction(false);
      }
    }
  }

  async function handleMove(direction: string) {
    setPendingMove(true);
    const requestSessionId = sessionId;
    const previousVars = vars;
    try {
      const movement = await postSpatialMove(requestSessionId, direction);
      const summary = await getStateSummary(requestSessionId);
      if (isStaleSession(requestSessionId)) {
        return;
      }
      const serverVars = normalizeVars(summary.variables);
      const nextScene = await postNext(
        requestSessionId,
        toNextPayloadVars(serverVars, false),
      );
      if (isStaleSession(requestSessionId)) {
        return;
      }
      const nextVars = normalizeVars(nextScene.vars);

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
      await Promise.all([
        refreshMemory(historyLimit, requestSessionId),
        refreshPlace(requestSessionId),
      ]);
    } catch (error) {
      if (isStaleSession(requestSessionId)) {
        return;
      }
      pushToast("Movement failed.", String(error));
    } finally {
      if (!isStaleSession(requestSessionId)) {
        setPendingMove(false);
      }
    }
  }

  async function handleFactSearch(query: string) {
    setPendingSearch(true);
    try {
      const response = await getWorldFacts(sessionId, query, 8);
      setFacts(response.facts ?? []);
    } catch (error) {
      pushToast("Could not recall matching facts.", String(error));
    } finally {
      setPendingSearch(false);
    }
  }

  async function handleResetSession() {
    setPendingScene(true);
    try {
      await postResetSession();
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
      setNeedsOnboarding(true);
      setBootstrapNonce((value) => value + 1);
      pushToast("Session reset.", "World cleared and reseeded.", "info");
    } catch (error) {
      pushToast("Session reset failed.", String(error));
    } finally {
      setPendingScene(false);
    }
  }

  function handleOnboardingSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const theme = worldThemeInput.trim();
    const character = characterInput.trim();
    if (!theme || !character) {
      pushToast(
        "Setup incomplete.",
        "Please answer both onboarding questions before starting.",
      );
      return;
    }

    const seededVars: VarsRecord = {
      ...vars,
      [WORLD_THEME_KEY]: theme,
      [PLAYER_ROLE_KEY]: character,
      [CHARACTER_PROFILE_KEY]: character,
    };
    persistVars(seededVars);
    setNeedsOnboarding(false);
    setSceneText("Weaving your world setup into the first scene...");
    setChanges([
      {
        id: makeId("evt"),
        text: `World setup: ${theme} | Character: ${character}`,
      },
    ]);
    setBootstrapNonce((value) => value + 1);
    pushToast("Setup captured.", "Generating an opening tailored to your setup.", "info");
  }

  const sessionLabel = useMemo(() => sessionId.slice(-12), [sessionId]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <h1>WorldWeaver Explorer</h1>
          <p>{mode === "reflect" ? "Reflect mode chronicle view" : "API-first Explore mode v1"}</p>
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
          </div>
          <span>Session ...{sessionLabel}</span>
          <button type="button" className="danger-btn" onClick={handleResetSession}>
            Reset session
          </button>
        </div>
      </header>

      {mode === "explore" ? (
        needsOnboarding ? (
          <section className="panel setup-shell" aria-live="polite">
            <header className="panel-header">
              <h2>Before We Begin</h2>
              <span className="panel-meta">Vision-guided onboarding</span>
            </header>
            <p className="muted">
              Define your starting theme and character first. These answers seed the
              opening LLM context.
            </p>
            <form className="setup-form" onSubmit={handleOnboardingSubmit}>
              <label className="setup-field">
                What kind of world theme do you want to explore?
                <input
                  type="text"
                  value={worldThemeInput}
                  maxLength={120}
                  placeholder="e.g. frontier mystery, occult city noir, hopeful solarpunk"
                  onChange={(event) => setWorldThemeInput(event.target.value)}
                />
              </label>
              <label className="setup-field">
                Who are you in this world?
                <input
                  type="text"
                  value={characterInput}
                  maxLength={120}
                  placeholder="e.g. exiled cartographer, apprentice witch, retired ranger"
                  onChange={(event) => setCharacterInput(event.target.value)}
                />
              </label>
              <button type="submit" className="choice-btn setup-submit" disabled={pendingScene}>
                Start this world
              </button>
            </form>
          </section>
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
                choices={choices}
                pending={anyPending}
                onChoose={handleChoice}
              />
              <FreeformInput pending={pendingAction} onSubmit={handleAction} />
              <WhatChangedStrip changes={changes} />
            </section>
          }
          placePanel={
            <PlacePanel
              vars={vars}
              directions={directions}
              leads={leads}
              pendingMove={pendingMove}
              onMove={handleMove}
            />
          }
        />
        )
      ) : (
        <ReflectView
          sessionId={sessionId}
          events={history}
          pending={pendingHistory}
          historyLimit={historyLimit}
          onRefreshHistory={refreshMemory}
        />
      )}

      <ErrorToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
