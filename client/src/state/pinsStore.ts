import type { WorldEvent } from "../types";

const PINS_KEY = "ww.client.memory_pins";
const MAX_PINS = 24;

function getStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.sessionStorage;
}

function normalizeFact(value: unknown): WorldEvent | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const raw = value as Record<string, unknown>;
  if (typeof raw.id !== "number" || typeof raw.summary !== "string" || typeof raw.event_type !== "string") {
    return null;
  }
  const delta =
    raw.world_state_delta && typeof raw.world_state_delta === "object" && !Array.isArray(raw.world_state_delta)
      ? (raw.world_state_delta as Record<string, unknown>)
      : {};
  return {
    id: raw.id,
    summary: raw.summary,
    event_type: raw.event_type,
    created_at: typeof raw.created_at === "string" ? raw.created_at : null,
    storylet_id: typeof raw.storylet_id === "number" ? raw.storylet_id : null,
    session_id: typeof raw.session_id === "string" ? raw.session_id : null,
    world_state_delta: delta,
  };
}

export function loadPinnedFacts(): WorldEvent[] {
  const storage = getStorage();
  if (!storage) {
    return [];
  }
  const raw = storage.getItem(PINS_KEY);
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }
    const facts = parsed.map(normalizeFact).filter((fact): fact is WorldEvent => fact !== null);
    return facts.slice(0, MAX_PINS);
  } catch {
    return [];
  }
}

export function savePinnedFacts(facts: WorldEvent[]): void {
  const storage = getStorage();
  if (!storage) {
    return;
  }
  storage.setItem(PINS_KEY, JSON.stringify(facts.slice(0, MAX_PINS)));
}

export function togglePinnedFact(
  currentPins: WorldEvent[],
  fact: WorldEvent,
): { pins: WorldEvent[]; isPinned: boolean } {
  const existingIndex = currentPins.findIndex((item) => item.id === fact.id);
  if (existingIndex >= 0) {
    const next = currentPins.filter((item) => item.id !== fact.id);
    return { pins: next, isPinned: false };
  }
  const next = [fact, ...currentPins].slice(0, MAX_PINS);
  return { pins: next, isPinned: true };
}
