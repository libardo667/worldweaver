import type { SpatialDirectionMap, VarsRecord } from "../types";

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

export function normalizeVars(value: unknown): VarsRecord {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as VarsRecord;
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
