import type { VarsRecord } from "../types";

const SESSION_ID_KEY = "ww.client.session_id";
const SESSION_VARS_KEY = "ww.client.session_vars";
const WHAT_CHANGED_COLLAPSED_KEY = "ww.client.what_changed_collapsed";

function randomSegment(): string {
  if (typeof crypto !== "undefined" && "getRandomValues" in crypto) {
    const bytes = new Uint32Array(2);
    crypto.getRandomValues(bytes);
    return `${bytes[0].toString(36)}${bytes[1].toString(36)}`;
  }
  return Math.random().toString(36).slice(2);
}

export function createSessionId(): string {
  return `ww-${Date.now().toString(36)}-${randomSegment().slice(0, 8)}`;
}

export function getOrCreateSessionId(): string {
  const existing = localStorage.getItem(SESSION_ID_KEY);
  if (existing) {
    return existing;
  }
  const created = createSessionId();
  localStorage.setItem(SESSION_ID_KEY, created);
  return created;
}

export function replaceSessionId(): string {
  const next = createSessionId();
  localStorage.setItem(SESSION_ID_KEY, next);
  return next;
}

export function loadSessionVars(): VarsRecord {
  const raw = localStorage.getItem(SESSION_VARS_KEY);
  if (!raw) {
    return {};
  }
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as VarsRecord;
    }
    return {};
  } catch {
    return {};
  }
}

export function saveSessionVars(vars: VarsRecord): void {
  localStorage.setItem(SESSION_VARS_KEY, JSON.stringify(vars));
}

export function clearSessionStorage(): void {
  localStorage.removeItem(SESSION_VARS_KEY);
  localStorage.removeItem(SESSION_ID_KEY);
  localStorage.removeItem(WHAT_CHANGED_COLLAPSED_KEY);
}

export function loadWhatChangedCollapsed(): boolean {
  return localStorage.getItem(WHAT_CHANGED_COLLAPSED_KEY) === "1";
}

export function saveWhatChangedCollapsed(collapsed: boolean): void {
  localStorage.setItem(WHAT_CHANGED_COLLAPSED_KEY, collapsed ? "1" : "0");
}
