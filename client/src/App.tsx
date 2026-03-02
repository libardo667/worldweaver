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

function formatValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (value === null || value === undefined) {
    return "none";
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
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

function summarizePayloadChanges(payload: VarsRecord, max = 6): ChangeItem[] {
  const items: ChangeItem[] = [];
  for (const [key, value] of Object.entries(payload).slice(0, max)) {
    if (
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      ("inc" in value || "dec" in value)
    ) {
      const inc = Number((value as { inc?: unknown }).inc ?? 0);
      const dec = Number((value as { dec?: unknown }).dec ?? 0);
      const delta = inc - dec;
      const sign = delta >= 0 ? "+" : "";
      items.push({ id: makeId("chg"), text: `${key} ${sign}${delta}` });
      continue;
    }
    items.push({ id: makeId("chg"), text: `${key} -> ${formatValue(value)}` });
  }
  return items;
}

function flattenActionChanges(raw: VarsRecord): VarsRecord {
  const out: VarsRecord = {};
  for (const [key, value] of Object.entries(raw)) {
    if (
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      (key === "environment" || key === "variables")
    ) {
      for (const [nestedKey, nestedValue] of Object.entries(value as VarsRecord)) {
        out[`${key}.${nestedKey}`] = nestedValue;
      }
      continue;
    }
    out[key] = value;
  }
  return out;
}

function diffVars(previousVars: VarsRecord, nextVars: VarsRecord, max = 8): ChangeItem[] {
  const keys = new Set<string>([
    ...Object.keys(previousVars),
    ...Object.keys(nextVars),
  ]);
  const changes: ChangeItem[] = [];

  for (const key of keys) {
    const before = previousVars[key];
    const after = nextVars[key];
    if (JSON.stringify(before) === JSON.stringify(after)) {
      continue;
    }
    if (before === undefined) {
      changes.push({
        id: makeId("diff"),
        text: `${key} added: ${formatValue(after)}`,
      });
    } else if (after === undefined) {
      changes.push({
        id: makeId("diff"),
        text: `${key} removed`,
      });
    } else {
      changes.push({
        id: makeId("diff"),
        text: `${key}: ${formatValue(before)} -> ${formatValue(after)}`,
      });
    }
    if (changes.length >= max) {
      break;
    }
  }

  return changes;
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

      const entries: ChangeItem[] = [
        { id: makeId("evt"), text: `Choice: ${choice.label}` },
        ...summarizePayloadChanges(normalizeVars(choice.set), 4),
        ...diffVars(previousVars, nextVars, 5),
      ];
      setChanges(entries.slice(0, 8));
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

      const entries: ChangeItem[] = [
        { id: makeId("evt"), text: `Action: ${actionText}` },
        ...summarizePayloadChanges(flattenActionChanges(normalizeVars(result.state_changes)), 4),
        ...diffVars(previousVars, nextVars, 5),
      ];
      setChanges(entries.slice(0, 8));
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
      setChanges([
        { id: makeId("evt"), text: movement.result },
        ...diffVars(previousVars, nextVars, 7),
      ]);
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

      <main className="layout-grid">
        <MemoryPanel
          events={history}
          facts={facts}
          searchPending={pendingSearch}
          onSearch={handleFactSearch}
        />

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

        <PlacePanel
          vars={vars}
          directions={directions}
          leads={leads}
          pendingMove={pendingMove}
          onMove={handleMove}
        />
      </main>

      <ErrorToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
