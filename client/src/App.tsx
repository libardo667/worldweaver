import { useEffect, useMemo, useState } from "react";

import {
  getSpatialNavigation,
  getStateSummary,
  getWorldFacts,
  getWorldHistory,
  postAction,
  postNext,
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


export default function App() {
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

  const anyPending = pendingScene || pendingAction || pendingMove;

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

  async function refreshMemory() {
    try {
      const memory = await getWorldHistory(sessionId, 20);
      setHistory(memory.events ?? []);
    } catch (error) {
      pushToast("Memory shimmered and blurred.", String(error));
    }
  }

  async function refreshPlace() {
    try {
      const spatial = await getSpatialNavigation(sessionId);
      setDirections(spatial.directions ?? []);
      setLeads(spatial.leads ?? []);
    } catch (error) {
      pushToast("Could not read nearby paths.", String(error));
    }
  }

  async function fetchScene(initialVars: VarsRecord, omitLocation = false) {
    const scene = await postNext(sessionId, toNextPayloadVars(initialVars, omitLocation));
    setSceneText(scene.text);
    setChoices(scene.choices ?? []);
    persistVars(normalizeVars(scene.vars));
  }

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      setPendingScene(true);
      try {
        await fetchScene(vars);
        await Promise.all([refreshMemory(), refreshPlace()]);
      } catch (error) {
        pushToast("The world did not answer.", String(error));
      } finally {
        if (active) {
          setPendingScene(false);
        }
      }
    }
    void bootstrap();
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  async function handleChoice(choice: Choice) {
    setPendingScene(true);
    const previousVars = vars;
    try {
      const predicted = applyLocalSet(previousVars, normalizeVars(choice.set));
      const scene = await postNext(sessionId, toNextPayloadVars(predicted));
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
      await Promise.all([refreshMemory(), refreshPlace()]);
    } catch (error) {
      pushToast("Choice failed to resolve.", String(error));
    } finally {
      setPendingScene(false);
    }
  }

  async function handleAction(actionText: string) {
    setPendingAction(true);
    const previousVars = vars;
    try {
      const result = await postAction(sessionId, actionText);
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
      await Promise.all([refreshMemory(), refreshPlace()]);
    } catch (error) {
      pushToast("Your action lost coherence.", String(error));
    } finally {
      setPendingAction(false);
    }
  }

  async function handleMove(direction: string) {
    setPendingMove(true);
    const previousVars = vars;
    try {
      const movement = await postSpatialMove(sessionId, direction);
      const summary = await getStateSummary(sessionId);
      const serverVars = normalizeVars(summary.variables);
      const nextScene = await postNext(sessionId, toNextPayloadVars(serverVars, false));
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
      await Promise.all([refreshMemory(), refreshPlace()]);
    } catch (error) {
      pushToast("Movement failed.", String(error));
    } finally {
      setPendingMove(false);
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

  function handleResetSession() {
    clearSessionStorage();
    const replacement = replaceSessionId();
    setSessionId(replacement);
    setSceneText("A new thread begins.");
    setChoices([]);
    setHistory([]);
    setFacts([]);
    setDirections([]);
    setLeads([]);
    setChanges([{ id: makeId("evt"), text: "Session reset and rethreaded." }]);
    persistVars({});
    pushToast("Session reset.", "A fresh traveler enters this world.", "info");
  }

  const sessionLabel = useMemo(() => sessionId.slice(-12), [sessionId]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <h1>WorldWeaver Explorer</h1>
          <p>API-first Explore mode v1</p>
        </div>
        <div className="topbar-meta">
          <span>Session ...{sessionLabel}</span>
          <button type="button" className="danger-btn" onClick={handleResetSession}>
            Reset session
          </button>
        </div>
      </header>

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

      <ErrorToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
