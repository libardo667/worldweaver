import type {
  PrefetchBudgetMetadata,
  PrefetchStatusResponse,
  ProjectionRef,
  ProjectionRefWire,
  SpatialDirectionMap,
  V3ClarityLevel,
  V3LaneSource,
  V3TurnMetadata,
  V3TurnMetadataWire,
  VarsRecord,
} from "../types";

export type ClientMode = "explore" | "reflect" | "create" | "constellation";

export const WORLD_THEME_KEY = "world_theme";
export const PLAYER_ROLE_KEY = "player_role";
export const CHARACTER_PROFILE_KEY = "character_profile";
export const SURPRISE_SAFE_ACTION = "Surprise me with a safe but intriguing turn that fits this world.";

const PREFERENCE_PREFIXES = ["pref.", "lens."];
const PREFERENCE_KEYS = new Set(["surprise_safe"]);

export const PROMPT_NOTICE_KEY = "pref.notice_first";
export const PROMPT_HOPE_KEY = "pref.one_hope";
export const PROMPT_FEAR_KEY = "pref.one_fear";
export const PROMPT_VIBE_KEY = "lens.vibe";

export const BLOCKED_MOVE_DETAIL = "Cannot move in that direction";
export const BLOCKED_MOVE_TOAST_COOLDOWN_MS = 8000;
export const PLACE_REFRESH_NOTICE_COOLDOWN_MS = 12000;
export const PLACE_REFRESH_NOTICE = "Nearby routes may be briefly out of date.";

function readEnvBoolean(value: unknown, fallback: boolean): boolean {
  const raw = String(value ?? "").trim().toLowerCase();
  if (raw.length === 0) {
    return fallback;
  }
  return raw === "1" || raw === "true" || raw === "yes";
}

export const ENABLE_CONSTELLATION = readEnvBoolean(
  import.meta.env.VITE_WW_ENABLE_CONSTELLATION,
  false,
);
export const ENABLE_DEV_RESET = readEnvBoolean(
  import.meta.env.VITE_WW_ENABLE_DEV_RESET,
  Boolean(import.meta.env.DEV),
);
export const SHOW_PREFETCH_STATUS = readEnvBoolean(
  import.meta.env.VITE_WW_SHOW_PREFETCH_STATUS,
  true,
);
export const ENABLE_ASSISTIVE_SPATIAL = readEnvBoolean(
  import.meta.env.VITE_WW_ENABLE_ASSISTIVE_SPATIAL,
  true,
);
export const ENABLE_TOPBAR_RUNTIME_STATUS_CHIPS = readEnvBoolean(
  import.meta.env.VITE_WW_ENABLE_TOPBAR_RUNTIME_STATUS_CHIPS,
  false,
);

export type RuntimeLaneState = "active" | "idle" | "off";
export type RuntimeBudgetHealth = "healthy" | "warming" | "cold" | "off";

export type TopbarRuntimeStatusModel = {
  summaryText: string;
  summaryActive: boolean;
  chipsEnabled: boolean;
  laneStates: Record<"scene" | "world" | "player", RuntimeLaneState>;
  budget: {
    label: string;
    health: RuntimeBudgetHealth;
  };
};

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

const V3_LANE_SOURCES = new Set(["world", "scene", "player"]);
const V3_CLARITY_LEVELS = new Set(["low", "medium", "high"]);

export function normalizeVars(value: unknown): VarsRecord {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as VarsRecord;
}

function normalizeV3LaneSource(raw: unknown): V3LaneSource {
  const lane = String(raw ?? "").trim().toLowerCase();
  if (V3_LANE_SOURCES.has(lane)) {
    return lane as V3LaneSource;
  }
  return "unknown";
}

function normalizeV3ClarityLevel(raw: unknown): V3ClarityLevel {
  const clarity = String(raw ?? "").trim().toLowerCase();
  if (V3_CLARITY_LEVELS.has(clarity)) {
    return clarity as V3ClarityLevel;
  }
  return "unknown";
}

function normalizeProjectionRef(value: unknown): ProjectionRef | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const payload = value as ProjectionRefWire;
  const projectionId = String(payload.projection_id ?? "").trim() || null;
  const canonCommitId = String(payload.canon_commit_id ?? "").trim() || null;
  const branchId = String(payload.branch_id ?? "").trim() || null;
  if (!projectionId && !canonCommitId && !branchId) {
    return null;
  }
  return {
    projection_id: projectionId,
    canon_commit_id: canonCommitId,
    branch_id: branchId,
  };
}

function extractV3TurnMetadataWire(value: unknown): V3TurnMetadataWire | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const payload = value as Record<string, unknown>;
  const nested = payload.v3;
  if (nested && typeof nested === "object" && !Array.isArray(nested)) {
    return nested as V3TurnMetadataWire;
  }
  const hasTopLevelV3Fields =
    "lane_source" in payload || "clarity_level" in payload || "projection_ref" in payload;
  if (!hasTopLevelV3Fields) {
    return null;
  }
  return {
    lane_source: payload.lane_source as string | null | undefined,
    clarity_level: payload.clarity_level as string | null | undefined,
    projection_ref: payload.projection_ref as ProjectionRefWire | null | undefined,
  };
}

export function parseV3TurnMetadata(value: unknown): V3TurnMetadata | null {
  const wire = extractV3TurnMetadataWire(value);
  if (!wire) {
    return null;
  }
  return {
    lane_source: normalizeV3LaneSource(wire.lane_source),
    clarity_level: normalizeV3ClarityLevel(wire.clarity_level),
    projection_ref: normalizeProjectionRef(wire.projection_ref),
  };
}

export function makeId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function toNextPayloadVars(vars: VarsRecord, omitLocation = false): VarsRecord {
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

export function buildChoiceTakenDelta(setPayload: VarsRecord) {
  const delta = {
    set: [] as { key: string; value: unknown }[],
    increment: [] as { key: string; amount: number }[],
    append_fact: [],
  };
  for (const [key, value] of Object.entries(setPayload)) {
    if (
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      ("inc" in value || "dec" in value)
    ) {
      const inc = Number((value as { inc?: unknown }).inc ?? 0);
      const dec = Number((value as { dec?: unknown }).dec ?? 0);
      delta.increment.push({ key, amount: inc - dec });
    } else {
      delta.set.push({ key, value });
    }
  }
  return delta;
}

export function readStringVar(vars: VarsRecord, key: string): string {
  const raw = vars[key];
  if (typeof raw !== "string") {
    return "";
  }
  return raw.trim();
}

function isPreferenceVar(key: string): boolean {
  return PREFERENCE_KEYS.has(key) || PREFERENCE_PREFIXES.some((prefix) => key.startsWith(prefix));
}

export function getErrorDetail(error: unknown): string {
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

export function extractPreferenceVars(vars: VarsRecord): VarsRecord {
  const out: VarsRecord = {};
  for (const [key, value] of Object.entries(vars)) {
    if (isPreferenceVar(key)) {
      out[key] = value;
    }
  }
  return out;
}

export function mergePreferenceVars(serverVars: VarsRecord, localVars: VarsRecord): VarsRecord {
  return {
    ...serverVars,
    ...extractPreferenceVars(localVars),
  };
}

export function toAccessibleDirectionMap(directions: string[]): SpatialDirectionMap {
  const map: SpatialDirectionMap = {};
  for (const direction of directions) {
    const key = String(direction ?? "").trim().toLowerCase();
    if (!key) {
      continue;
    }
    map[key] = { accessible: true, reason: null };
  }
  return map;
}

export function buildPromptVars({
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

function formatBudgetHealthLabel(health: RuntimeBudgetHealth): string {
  if (health === "healthy") {
    return "Budget: healthy";
  }
  if (health === "warming") {
    return "Budget: warming";
  }
  if (health === "cold") {
    return "Budget: cold";
  }
  return "Budget: off";
}

function deriveBudgetHealth(
  prefetchStatus: PrefetchStatusResponse | null,
  prefetchBudget: PrefetchBudgetMetadata | null,
  needsOnboarding: boolean,
): RuntimeBudgetHealth {
  if (needsOnboarding) {
    return "off";
  }
  if (prefetchBudget) {
    if (prefetchBudget.budget_ms <= 0 || prefetchBudget.max_nodes <= 0) {
      return "off";
    }
  }
  if (!prefetchStatus) {
    return "cold";
  }
  const stubsCached = Math.max(0, Number(prefetchStatus.stubs_cached ?? 0) || 0);
  const expiresInSeconds = Math.max(
    0,
    Number(prefetchStatus.expires_in_seconds ?? 0) || 0,
  );
  if (stubsCached <= 0 || expiresInSeconds <= 0) {
    return "cold";
  }
  if (stubsCached < 2 || expiresInSeconds < 30) {
    return "warming";
  }
  return "healthy";
}

export function buildTopbarRuntimeStatus(args: {
  anyBusy: boolean;
  backendNotice: string;
  pendingScene: boolean;
  pendingAction: boolean;
  pendingMove: boolean;
  prefetchStatus: PrefetchStatusResponse | null;
  prefetchBudget: PrefetchBudgetMetadata | null;
  needsOnboarding: boolean;
}): TopbarRuntimeStatusModel {
  const budgetHealth = deriveBudgetHealth(
    args.prefetchStatus,
    args.prefetchBudget,
    args.needsOnboarding,
  );
  return {
    summaryText:
      args.anyBusy && args.backendNotice ? args.backendNotice : "Backend ready",
    summaryActive: args.anyBusy,
    chipsEnabled: ENABLE_TOPBAR_RUNTIME_STATUS_CHIPS,
    laneStates: {
      scene: args.anyBusy ? "active" : "idle",
      world: args.pendingScene ? "active" : args.needsOnboarding ? "off" : "idle",
      player:
        args.pendingAction || args.pendingMove
          ? "active"
          : args.needsOnboarding
            ? "off"
            : "idle",
    },
    budget: {
      label: formatBudgetHealthLabel(budgetHealth),
      health: budgetHealth,
    },
  };
}
