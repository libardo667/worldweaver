import type {
  PrefetchBudgetMetadata,
  PrefetchStatusResponse,
  ProjectionRef,
  VarsRecord,
} from "../types";

const SESSION_ID_KEY = "ww.client.session_id";
const SESSION_VARS_KEY = "ww.client.session_vars";
const WHAT_CHANGED_COLLAPSED_KEY = "ww.client.what_changed_collapsed";
const ONBOARDED_SESSION_ID_KEY = "ww.client.onboarded_session_id";
const ONBOARDED_WORLD_ID_KEY = "ww.client.onboarded_world_id";
const PREFETCH_STATUS_CACHE_PREFIX = "ww.client.prefetch_status.";
const PREFETCH_BUDGET_CACHE_PREFIX = "ww.client.prefetch_budget.";

export type PrefetchCacheScope = {
  sessionId: string;
  projectionRef?: ProjectionRef | null;
};

function randomSegment(): string {
  if (typeof crypto !== "undefined" && "getRandomValues" in crypto) {
    const bytes = new Uint32Array(2);
    crypto.getRandomValues(bytes);
    return `${bytes[0].toString(36)}${bytes[1].toString(36)}`;
  }
  return Math.random().toString(36).slice(2);
}

function normalizeStorageToken(value: unknown): string {
  return encodeURIComponent(String(value ?? "").trim());
}

function buildProjectionScopeToken(projectionRef?: ProjectionRef | null): string {
  const projectionId = String(projectionRef?.projection_id ?? "").trim();
  const canonCommitId = String(projectionRef?.canon_commit_id ?? "").trim();
  const branchId = String(projectionRef?.branch_id ?? "").trim();
  if (!projectionId && !canonCommitId && !branchId) {
    return "session";
  }
  return [projectionId, canonCommitId, branchId]
    .map((value) => normalizeStorageToken(value || "_"))
    .join("|");
}

function buildPrefetchCacheKey(prefix: string, scope: PrefetchCacheScope): string {
  return `${prefix}${normalizeStorageToken(scope.sessionId)}.${buildProjectionScopeToken(scope.projectionRef)}`;
}

function parseJsonObject(raw: string | null): Record<string, unknown> | null {
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return null;
    }
    return parsed as Record<string, unknown>;
  } catch {
    return null;
  }
}

function parseNonNegativeInteger(value: unknown): number | null {
  if (value === undefined || value === null) {
    return null;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return Math.max(0, Math.floor(parsed));
}

function clearStoragePrefix(prefix: string): void {
  const keysToClear: string[] = [];
  for (let index = 0; index < localStorage.length; index += 1) {
    const key = localStorage.key(index);
    if (key && key.startsWith(prefix)) {
      keysToClear.push(key);
    }
  }
  for (const key of keysToClear) {
    localStorage.removeItem(key);
  }
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
  localStorage.removeItem(ONBOARDED_SESSION_ID_KEY);
  clearStoragePrefix(PREFETCH_STATUS_CACHE_PREFIX);
  clearStoragePrefix(PREFETCH_BUDGET_CACHE_PREFIX);
}

export function loadWhatChangedCollapsed(): boolean {
  return localStorage.getItem(WHAT_CHANGED_COLLAPSED_KEY) === "1";
}

export function saveWhatChangedCollapsed(collapsed: boolean): void {
  localStorage.setItem(WHAT_CHANGED_COLLAPSED_KEY, collapsed ? "1" : "0");
}

export function getOnboardedSessionId(): string {
  return localStorage.getItem(ONBOARDED_SESSION_ID_KEY) ?? "";
}

export function setOnboardedSessionId(sessionId: string): void {
  localStorage.setItem(ONBOARDED_SESSION_ID_KEY, sessionId);
}

export function getOnboardedWorldId(): string {
  return localStorage.getItem(ONBOARDED_WORLD_ID_KEY) ?? "";
}

export function setOnboardedWorldId(worldId: string): void {
  localStorage.setItem(ONBOARDED_WORLD_ID_KEY, worldId);
}

export function clearOnboardedSession(): void {
  localStorage.removeItem(ONBOARDED_SESSION_ID_KEY);
  localStorage.removeItem(ONBOARDED_WORLD_ID_KEY);
}

export function loadPrefetchStatusCache(
  scope: PrefetchCacheScope,
): PrefetchStatusResponse | null {
  const payload = parseJsonObject(
    localStorage.getItem(buildPrefetchCacheKey(PREFETCH_STATUS_CACHE_PREFIX, scope)),
  );
  if (!payload) {
    return null;
  }
  const stubsCached = parseNonNegativeInteger(payload.stubs_cached);
  const expiresInSeconds = parseNonNegativeInteger(payload.expires_in_seconds);
  if (stubsCached === null || expiresInSeconds === null) {
    return null;
  }
  return {
    stubs_cached: stubsCached,
    expires_in_seconds: expiresInSeconds,
  };
}

export function savePrefetchStatusCache(
  scope: PrefetchCacheScope,
  status: PrefetchStatusResponse,
): void {
  const normalized: PrefetchStatusResponse = {
    stubs_cached: Math.max(0, Number(status.stubs_cached ?? 0) || 0),
    expires_in_seconds: Math.max(0, Number(status.expires_in_seconds ?? 0) || 0),
  };
  localStorage.setItem(
    buildPrefetchCacheKey(PREFETCH_STATUS_CACHE_PREFIX, scope),
    JSON.stringify(normalized),
  );
}

export function loadPrefetchBudgetCache(
  scope: PrefetchCacheScope,
): PrefetchBudgetMetadata | null {
  const payload = parseJsonObject(
    localStorage.getItem(buildPrefetchCacheKey(PREFETCH_BUDGET_CACHE_PREFIX, scope)),
  );
  if (!payload) {
    return null;
  }
  const budgetMs = parseNonNegativeInteger(payload.budget_ms);
  const maxNodes = parseNonNegativeInteger(payload.max_nodes);
  const expansionDepth = parseNonNegativeInteger(payload.expansion_depth);
  if (budgetMs === null || maxNodes === null || expansionDepth === null) {
    return null;
  }
  return {
    budget_ms: budgetMs,
    max_nodes: maxNodes,
    expansion_depth: expansionDepth,
  };
}

export function savePrefetchBudgetCache(
  scope: PrefetchCacheScope,
  budget: PrefetchBudgetMetadata,
): void {
  const normalized: PrefetchBudgetMetadata = {
    budget_ms: Math.max(0, Number(budget.budget_ms ?? 0) || 0),
    max_nodes: Math.max(0, Number(budget.max_nodes ?? 0) || 0),
    expansion_depth: Math.max(0, Number(budget.expansion_depth ?? 0) || 0),
  };
  localStorage.setItem(
    buildPrefetchCacheKey(PREFETCH_BUDGET_CACHE_PREFIX, scope),
    JSON.stringify(normalized),
  );
}

export function clearPrefetchBudgetCache(scope: PrefetchCacheScope): void {
  localStorage.removeItem(buildPrefetchCacheKey(PREFETCH_BUDGET_CACHE_PREFIX, scope));
}
