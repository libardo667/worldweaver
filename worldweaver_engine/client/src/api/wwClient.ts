// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import type {
  DevHardResetResponse,
  LeaveSessionResponse,
  ResetSessionResponse,
  WorldFactsResponse,
  WorldHistoryResponse,
  SettingsReadinessResponse,
} from "../types";
import { getJwt } from "../state/sessionStore";
import type { ShardInfo } from "../types";

// Mutable API base — updated when the user switches cities.
// Initialised from localStorage so the choice persists across page reloads.
let _apiBase: string =
  localStorage.getItem("ww.client.selected_shard_url") ??
  (import.meta.env.VITE_WW_API_BASE as string | undefined) ??
  "";

export class ApiRequestError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

export function isApiRequestError(value: unknown): value is ApiRequestError {
  return value instanceof ApiRequestError;
}

function getWindowOrigin(): string {
  if (typeof window === "undefined") {
    return "http://localhost";
  }
  return window.location.origin;
}

function isMixedContentUnsafe(url: string): boolean {
  const raw = String(url || "").trim();
  if (!raw || typeof window === "undefined") {
    return false;
  }
  try {
    const parsed = new URL(raw, getWindowOrigin());
    return window.location.protocol === "https:" && parsed.protocol === "http:";
  } catch {
    return false;
  }
}

function getEffectiveApiBase(): string {
  return isMixedContentUnsafe(_apiBase) ? "" : _apiBase;
}

function summarizeErrorBody(body: string, status: number): string {
  const raw = String(body || "").trim();
  if (!raw) {
    return `Request failed with status ${status}`;
  }

  const lower = raw.toLowerCase();
  const looksLikeHtml =
    lower.includes("<html") ||
    lower.includes("<!doctype") ||
    lower.includes("<body") ||
    lower.includes("<head");

  if (looksLikeHtml) {
    if (lower.includes("error 524") || lower.includes("cloudflare") && lower.includes("524")) {
      return "The public site timed out waiting for the shard to respond (Cloudflare 524). Try again in a moment.";
    }
    if (lower.includes("error 504") || lower.includes("gateway timeout")) {
      return "The request timed out before the shard responded.";
    }
    if (lower.includes("error 502") || lower.includes("bad gateway")) {
      return "The public proxy could not reach the shard backend.";
    }
    if (lower.includes("error 403") || lower.includes("forbidden")) {
      return "The public site rejected the request before it reached the shard.";
    }
    return `Request failed with status ${status}`;
  }

  const singleLine = raw.replace(/\s+/g, " ").trim();
  return singleLine.length > 240 ? `${singleLine.slice(0, 237)}...` : singleLine;
}

function buildApiRequestError(status: number, body: string): ApiRequestError {
  const raw = String(body || "").trim();
  let code: string | undefined;
  let message = summarizeErrorBody(raw, status);

  if (raw) {
    try {
      const parsed = JSON.parse(raw) as {
        detail?: { message?: string; error?: string } | string;
        message?: string;
        error?: string;
      };
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        message = parsed.detail.trim();
      } else if (parsed.detail && typeof parsed.detail === "object") {
        if (typeof parsed.detail.message === "string" && parsed.detail.message.trim()) {
          message = parsed.detail.message.trim();
        }
        if (typeof parsed.detail.error === "string" && parsed.detail.error.trim()) {
          code = parsed.detail.error.trim();
        }
      } else if (typeof parsed.message === "string" && parsed.message.trim()) {
        message = parsed.message.trim();
      }
      if (!code && typeof parsed.error === "string" && parsed.error.trim()) {
        code = parsed.error.trim();
      }
    } catch {
      // Keep the summarized fallback when the response body is not JSON.
    }
  }

  return new ApiRequestError(message, status, code);
}

export function setApiBase(url: string): void {
  _apiBase = url;
}

export function getApiBase(): string {
  return getEffectiveApiBase();
}

export function hasMixedContentApiBase(): boolean {
  return isMixedContentUnsafe(_apiBase);
}

function browserUrlForShard(shard: ShardInfo): string {
  const raw = String(import.meta.env.VITE_WW_SHARD_ROUTES ?? "").trim();
  if (raw) {
    try {
      const routes = JSON.parse(raw) as Record<string, { prefix?: string }>;
      const prefix = String(routes[shard.shard_id]?.prefix ?? "").trim();
      if (prefix.startsWith("/")) return prefix.replace(/\/$/, "");
    } catch {
      // A standalone client may have no generated local route table.
    }
  }
  return shard.shard_url;
}

export async function fetchShards(): Promise<ShardInfo[]> {
  try {
    // Use the Vite proxy path so this stays same-origin on HTTPS (world-weaver.org).
    // Vite rewrites /ww-world/* → VITE_WW_WORLD_URL/* server-side.
    const resp = await fetch(`/ww-world/api/federation/shards`);
    if (!resp.ok) return [];
    const data = await resp.json() as { shards: Omit<ShardInfo, "browser_url">[] };
    return (data.shards ?? []).map((shard) => ({
      ...shard,
      browser_url: browserUrlForShard({ ...shard, browser_url: "" }),
    }));
  } catch {
    return [];
  }
}

async function requestJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const jwt = getJwt();
  const authHeader: Record<string, string> = jwt ? { Authorization: `Bearer ${jwt}` } : {};
  const response = await fetch(`${getEffectiveApiBase()}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...authHeader,
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const body = await response.text();
    throw buildApiRequestError(response.status, body);
  }

  return (await response.json()) as T;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export type AuthResponse = {
  token: string;
  actor_id: string;
  player_id: string;
  username: string;
  display_name: string;
  pass_type: string;
  pass_expires_at: string | null;
  terms_text: string;
};

export type RegisterPayload = {
  email: string;
  username: string;
  display_name: string;
  password: string;
  pass_type?: string;
  terms_accepted: boolean;
};

export function postRegister(payload: RegisterPayload): Promise<AuthResponse> {
  return requestJson<AuthResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function postLogin(identifier: string, password: string): Promise<AuthResponse> {
  return requestJson<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ identifier, password }),
  });
}

export function postRequestPasswordReset(identifier: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>("/api/auth/request-password-reset", {
    method: "POST",
    body: JSON.stringify({ identifier }),
  });
}

export function postResetPassword(payload: {
  token: string;
  new_password: string;
}): Promise<AuthResponse> {
  return requestJson<AuthResponse>("/api/auth/reset-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getAuthMe(): Promise<AuthResponse> {
  return requestJson<AuthResponse>("/api/auth/me");
}

export type ShardCapability = {
  id: string;
  title: string;
  description: string;
};

export type ShardExperienceResponse = {
  shard_id: string;
  experience_type: "commons" | "game";
  game_rules_active: boolean;
  entry_disclosure: {
    title: string;
    summary: string;
    capabilities: ShardCapability[];
  };
};

export type SituatedWorldObject = {
  object_id: string;
  name: string;
  description: string;
  object_kind: string;
  relation: "carried" | "here" | string;
  can_pick_up: boolean;
  revision: number;
};

export type WorldObjectsResponse = {
  objects: SituatedWorldObject[];
  count: number;
};

export type LocalMaterial = {
  material_id: string;
  title: string;
  description: string;
  available_units: number;
  capacity_units: number;
};

export type LocalRecipe = {
  recipe_id: string;
  title: string;
  description: string;
  can_make: boolean;
  missing_units: Record<string, number>;
};

export type LocalMakingResponse = {
  location: string;
  materials: LocalMaterial[];
  recipes: LocalRecipe[];
};

export type LocalStoop = {
  stoop_id: string;
  title: string;
  prompt: string;
  location: string;
  capacity: number;
  active_count: number;
  space_remaining: number;
};

export type LocalStoopsResponse = {
  location: string;
  stoops: LocalStoop[];
  count: number;
};

export type StoopEntry = {
  entry_id: string;
  object: Omit<SituatedWorldObject, "relation" | "can_pick_up">;
  can_take: boolean;
  can_withdraw: boolean;
};

export type WorldStoopResponse = {
  stoop: LocalStoop;
  entries: StoopEntry[];
  count: number;
};

export type WorldStoopCommandResponse = {
  ok: boolean;
  replayed: boolean;
  stoop: LocalStoop;
  entry: StoopEntry;
  receipt: {
    receipt_id: string;
    operation: string;
    entry_id: string;
  };
};

export type MakeWorldObjectResponse = {
  ok: boolean;
  replayed: boolean;
  object: Omit<SituatedWorldObject, "relation" | "can_pick_up">;
  receipt: {
    receipt_id: string;
    operation: string;
    object_id: string;
  };
};

export type ObjectCommandResponse = {
  ok: boolean;
  replayed: boolean;
  object: Omit<SituatedWorldObject, "relation" | "can_pick_up">;
  receipt: {
    receipt_id: string;
    operation: string;
    object_id: string;
  };
};

export type ObjectExchange = {
  exchange_id: string;
  status: "open" | "completed" | "declined" | "cancelled" | string;
  proposer_actor_id: string;
  recipient_actor_id: string;
  offered_object: Omit<SituatedWorldObject, "relation" | "can_pick_up">;
  requested_object: Omit<SituatedWorldObject, "relation" | "can_pick_up">;
  viewer_role: "proposer" | "recipient" | "observer";
  counterpart_present: boolean;
  can_accept: boolean;
  can_decline: boolean;
  can_cancel: boolean;
};

export type ObjectExchangeOfferOption = {
  recipient_actor_id: string;
  recipient_session_id: string;
  requested_objects: Array<Omit<SituatedWorldObject, "relation" | "can_pick_up">>;
};

export type ObjectExchangesResponse = {
  exchanges: ObjectExchange[];
  count: number;
  offer_options: ObjectExchangeOfferOption[];
};

export type ObjectExchangeCommandResponse = {
  ok: boolean;
  replayed: boolean;
  exchange: ObjectExchange;
  receipt: {
    receipt_id: string;
    operation: string;
    exchange_id: string;
  };
};

export type SpaceAccessStatus = {
  location: string;
  mode: "public" | "requestable" | "private" | "closed";
  note: string;
  revision: number;
  is_controller: boolean;
  admitted: boolean;
  can_enter: boolean;
  can_request: boolean;
  entry_reason: string;
  active_grants: Array<{ actor_id: string; session_id: string }>;
};

export type SpaceAccessRequest = {
  request_id: string;
  requester_actor_id: string;
  requester_session_id: string;
  note: string;
  status: string;
  created_at?: string | null;
};

export type SpaceAccessCommandResponse = {
  ok: boolean;
  replayed: boolean;
  receipt: {
    receipt_id: string;
    operation: string;
    location: string;
    result: Record<string, unknown>;
  };
};

export function getShardExperience(): Promise<ShardExperienceResponse> {
  return requestJson<ShardExperienceResponse>("/api/shard/experience");
}

export function getWorldObjects(sessionId: string): Promise<WorldObjectsResponse> {
  const params = new URLSearchParams({ session_id: sessionId });
  return requestJson<WorldObjectsResponse>(`/api/world/objects?${params.toString()}`);
}

export function getObjectExchanges(sessionId: string): Promise<ObjectExchangesResponse> {
  const params = new URLSearchParams({ session_id: sessionId });
  return requestJson<ObjectExchangesResponse>(`/api/world/exchanges?${params.toString()}`);
}

export function getSpaceAccessStatus(sessionId: string, location: string): Promise<{ access: SpaceAccessStatus }> {
  const params = new URLSearchParams({ session_id: sessionId, location });
  return requestJson<{ access: SpaceAccessStatus }>(`/api/world/access?${params.toString()}`);
}

export function getPendingSpaceAccessRequests(
  sessionId: string,
  location: string,
): Promise<{ location: string; requests: SpaceAccessRequest[]; count: number }> {
  const params = new URLSearchParams({ session_id: sessionId, location });
  return requestJson<{ location: string; requests: SpaceAccessRequest[]; count: number }>(
    `/api/world/access/requests?${params.toString()}`,
  );
}

export function getLocalMaking(sessionId: string): Promise<LocalMakingResponse> {
  const params = new URLSearchParams({ session_id: sessionId });
  return requestJson<LocalMakingResponse>(`/api/world/making?${params.toString()}`);
}

export function getLocalStoops(sessionId: string): Promise<LocalStoopsResponse> {
  const params = new URLSearchParams({ session_id: sessionId });
  return requestJson<LocalStoopsResponse>(`/api/world/stoops?${params.toString()}`);
}

export function getWorldStoop(sessionId: string, stoopId: string): Promise<WorldStoopResponse> {
  const params = new URLSearchParams({ session_id: sessionId });
  return requestJson<WorldStoopResponse>(`/api/world/stoops/${encodeURIComponent(stoopId)}?${params.toString()}`);
}

export function postLeaveObjectOnStoop(
  sessionId: string,
  stoopId: string,
  objectId: string,
  idempotencyKey: string,
): Promise<WorldStoopCommandResponse> {
  return requestJson<WorldStoopCommandResponse>(`/api/world/stoops/${encodeURIComponent(stoopId)}/leave`, {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, object_id: objectId, idempotency_key: idempotencyKey }),
  });
}

export function postTakeStoopObject(
  sessionId: string,
  entryId: string,
  idempotencyKey: string,
): Promise<WorldStoopCommandResponse> {
  return requestJson<WorldStoopCommandResponse>(`/api/world/stoops/entries/${encodeURIComponent(entryId)}/take`, {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, idempotency_key: idempotencyKey }),
  });
}

export function postWithdrawStoopObject(
  sessionId: string,
  entryId: string,
  idempotencyKey: string,
): Promise<WorldStoopCommandResponse> {
  return requestJson<WorldStoopCommandResponse>(`/api/world/stoops/entries/${encodeURIComponent(entryId)}/withdraw`, {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, idempotency_key: idempotencyKey }),
  });
}

export function postMakeWorldObject(
  sessionId: string,
  recipeId: string,
  idempotencyKey: string,
): Promise<MakeWorldObjectResponse> {
  return requestJson<MakeWorldObjectResponse>("/api/world/make", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      recipe_id: recipeId,
      idempotency_key: idempotencyKey,
    }),
  });
}

export function postPlaceWorldObject(
  sessionId: string,
  objectId: string,
  idempotencyKey: string,
): Promise<ObjectCommandResponse> {
  return requestJson<ObjectCommandResponse>(`/api/world/objects/${encodeURIComponent(objectId)}/place`, {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, idempotency_key: idempotencyKey }),
  });
}

export function postPickUpWorldObject(
  sessionId: string,
  objectId: string,
  idempotencyKey: string,
): Promise<ObjectCommandResponse> {
  return requestJson<ObjectCommandResponse>(`/api/world/objects/${encodeURIComponent(objectId)}/pick-up`, {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, idempotency_key: idempotencyKey }),
  });
}

export function postGiveWorldObject(
  sessionId: string,
  objectId: string,
  recipientSessionId: string,
  idempotencyKey: string,
): Promise<ObjectCommandResponse> {
  return requestJson<ObjectCommandResponse>(`/api/world/objects/${encodeURIComponent(objectId)}/give`, {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      recipient_session_id: recipientSessionId,
      idempotency_key: idempotencyKey,
    }),
  });
}

export function postObjectExchangeOffer(
  sessionId: string,
  recipientSessionId: string,
  offeredObjectId: string,
  requestedObjectId: string,
  idempotencyKey: string,
): Promise<ObjectExchangeCommandResponse> {
  return requestJson<ObjectExchangeCommandResponse>("/api/world/exchanges", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      recipient_session_id: recipientSessionId,
      offered_object_id: offeredObjectId,
      requested_object_id: requestedObjectId,
      idempotency_key: idempotencyKey,
    }),
  });
}

export function postObjectExchangeDecision(
  sessionId: string,
  exchangeId: string,
  decision: "accept" | "decline" | "cancel",
  idempotencyKey: string,
): Promise<ObjectExchangeCommandResponse> {
  return requestJson<ObjectExchangeCommandResponse>(
    `/api/world/exchanges/${encodeURIComponent(exchangeId)}/${decision}`,
    {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, idempotency_key: idempotencyKey }),
    },
  );
}

export function postSpaceAccessRequest(
  sessionId: string,
  location: string,
  idempotencyKey: string,
): Promise<SpaceAccessCommandResponse> {
  return requestJson<SpaceAccessCommandResponse>("/api/world/access/requests", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, location, note: "", idempotency_key: idempotencyKey }),
  });
}

export function postSpaceAccessResolution(
  sessionId: string,
  requestId: string,
  decision: "admitted" | "denied",
  idempotencyKey: string,
): Promise<SpaceAccessCommandResponse> {
  return requestJson<SpaceAccessCommandResponse>(
    `/api/world/access/requests/${encodeURIComponent(requestId)}/resolve`,
    {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, decision, idempotency_key: idempotencyKey }),
    },
  );
}

export function postSpaceAccessMode(
  sessionId: string,
  location: string,
  mode: "public" | "requestable" | "private" | "closed",
  idempotencyKey: string,
): Promise<SpaceAccessCommandResponse> {
  return requestJson<SpaceAccessCommandResponse>("/api/world/access/mode", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, location, mode, idempotency_key: idempotencyKey }),
  });
}

export function postSpaceAdmission(
  sessionId: string,
  recipientSessionId: string,
  location: string,
  command: "invite" | "revoke",
  idempotencyKey: string,
): Promise<SpaceAccessCommandResponse> {
  return requestJson<SpaceAccessCommandResponse>(`/api/world/access/${command}`, {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      recipient_session_id: recipientSessionId,
      location,
      idempotency_key: idempotencyKey,
    }),
  });
}

export function getWorldHistory(
  sessionId: string,
  limit = 25,
): Promise<WorldHistoryResponse> {
  const params = new URLSearchParams({
    session_id: sessionId,
    limit: String(limit),
  });
  return requestJson<WorldHistoryResponse>(`/api/world/history?${params.toString()}`);
}

export function getWorldFacts(
  sessionId: string,
  query: string,
  limit = 12,
): Promise<WorldFactsResponse> {
  const params = new URLSearchParams({
    session_id: sessionId,
    query,
    limit: String(limit),
  });
  return requestJson<WorldFactsResponse>(`/api/world/facts?${params.toString()}`);
}

export function postResetSession(): Promise<ResetSessionResponse> {
  return requestJson<ResetSessionResponse>("/api/reset-session", {
    method: "POST",
  });
}

export function postLeaveSession(sessionId: string): Promise<LeaveSessionResponse> {
  return requestJson<LeaveSessionResponse>("/api/session/leave", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export function postDevHardReset(): Promise<DevHardResetResponse> {
  return requestJson<DevHardResetResponse>("/api/dev/hard-reset", {
    method: "POST",
  });
}

export function getSettingsReadiness(): Promise<SettingsReadinessResponse> {
  return requestJson<SettingsReadinessResponse>("/api/settings/readiness");
}

export type DigestRosterEntry = {
  session_id: string;
  location: string;
  last_seen: string | null;
  player_name: string | null;
  display_name: string | null;
  entity_type?: "agent" | "human" | string | null;
  status?: "active" | "resting" | "returning" | string | null;
};

export type DigestTimelineEntry = {
  ts: string | null;
  who: string | null;
  display_name: string | null;
  summary: string;
  narrative?: string | null;
  location: string | null;
  destination?: string | null;
  is_movement?: boolean;
};

export type LocationGraphNode = {
  key: string;
  name: string;
  node_type?: string;
  count: number;
  agent_count?: number;
  present_count?: number;
  present_names?: string[];
  agent_names?: string[];
  player_names?: string[];
  is_player: boolean;
  lat?: number | null;
  lon?: number | null;
  description?: string;
  parent_location?: string | null;
};

export type LocationGraphEdge = {
  from: string;
  to: string;
};

export type LocationChatEntry = {
  id: number;
  session_id: string;
  display_name: string | null;
  message: string;
  ts: string | null;
};

export type WorldDigestResponse = {
  world_id: string | null;
  seeded: boolean;
  active_sessions: number;
  roster: DigestRosterEntry[];
  location_population: Record<string, number>;
  location_graph: { nodes: LocationGraphNode[]; edges: LocationGraphEdge[] } | null;
  timeline: DigestTimelineEntry[];
  events_shown: number;
  known_agents: string[];
  known_contacts?: DMRecipient[];
  player_location: string | null;
  location_chat?: LocationChatEntry[];
};

export type RestMetricsSession = {
  session_id: string;
  display_name: string;
  player_name: string | null;
  entity_type: "agent" | "human" | string;
  location: string;
  last_updated_at: string | null;
  status: "active" | "resting" | "returning" | string;
  rest_reason: string | null;
  rest_derived: boolean;
  wakefulness: number | null;
  effective_arousal: number | null;
  rest_location: string | null;
  rest_started_at: string | null;
  rest_until: string | null;
  remaining_minutes: number | null;
  pending_reason: string | null;
  pending_location: string | null;
  pending_since: string | null;
  pending_hits: number;
  last_completed_at: string | null;
};

export type RestMetricsResponse = {
  generated_at: string;
  shard: {
    shard_id: string;
    city_id: string | null;
    shard_type: string;
  };
  counts: {
    total: number;
    active: number;
    resting: number;
    returning: number;
    pending_confirmation: number;
  };
  fractions: {
    active: number;
    resting: number;
    pending_confirmation: number;
  };
  sessions: RestMetricsSession[];
};

export function getWorldDigest(sessionId?: string, eventsLimit = 20): Promise<WorldDigestResponse> {
  const params = new URLSearchParams({ events_limit: String(eventsLimit) });
  if (sessionId) params.set("session_id", sessionId);
  return requestJson<WorldDigestResponse>(`/api/world/digest?${params.toString()}`);
}

export function getRestMetrics(includeActive = true): Promise<RestMetricsResponse> {
  const params = new URLSearchParams();
  if (includeActive) {
    params.set("include_active", "true");
  }
  const query = params.toString();
  return requestJson<RestMetricsResponse>(`/api/world/rest-metrics${query ? `?${query}` : ""}`);
}

export type EntryCard = {
  name: string;
  role: string;
  flavor: string;
  location: string;
  entry_action: string;
};

export type EntryNode = {
  name: string;
  key: string;
  lat: number | null;
  lon: number | null;
};

export type WorldEntryResponse = {
  world_id: string | null;
  snapshot: string;
  cards: EntryCard[];
  locations: string[];
  entry_nodes: EntryNode[];
};

export function getWorldEntry(): Promise<WorldEntryResponse> {
  return requestJson<WorldEntryResponse>("/api/world/entry");
}

export function postSessionBootstrap(
  sessionId: string,
  payload: {
    world_id: string;
    world_theme: string;
    player_role: string;
    entry_location?: string;
    bootstrap_source?: string;
  },
): Promise<{ success: boolean; session_id: string; vars: Record<string, unknown> }> {
  return requestJson("/api/session/bootstrap", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, ...payload }),
  });
}

export type DMRecipient = {
  key: string;
  label: string;
  recipient_type: "agent" | "player";
};

export function postDM(
  recipient: DMRecipient,
  fromName: string,
  body: string,
  sessionId?: string,
): Promise<{ success: boolean; dm_id: number; delivered_to: string; recipient_type: string; recipient_key: string }> {
  return requestJson("/api/world/dm", {
    method: "POST",
    body: JSON.stringify({
      recipient: recipient.key,
      recipient_type: recipient.recipient_type,
      from_name: fromName,
      body,
      ...(sessionId ? { session_id: sessionId } : {}),
    }),
  });
}

export type InboxDM = { filename: string; body: string; dm_id?: number };
export type DMThreadMessage = {
  dm_id: number;
  direction: "inbound" | "outbound";
  body: string;
  sent_at: string | null;
  read_at: string | null;
  from_name: string;
  to_name: string;
};
export type DMThread = {
  thread_key: string;
  counterpart: string;
  messages: DMThreadMessage[];
  last_at: string | null;
  unread_count: number;
};

export function getAgentInbox(
  agent: string,
): Promise<{ agent: string; letters: InboxDM[]; count: number }> {
  return requestJson(`/api/world/dm/inbox/${encodeURIComponent(agent)}`);
}

export function getPlayerInbox(
  sessionId: string,
): Promise<{ session_id: string; letters: InboxDM[]; count: number }> {
  return requestJson(`/api/world/dm/my-inbox/${encodeURIComponent(sessionId)}`);
}

export function getPlayerThreads(
  sessionId: string,
): Promise<{ session_id: string; threads: DMThread[]; count: number }> {
  return requestJson(`/api/world/dm/my-threads/${encodeURIComponent(sessionId)}`);
}

export function markPlayerThreadRead(
  sessionId: string,
  threadKey: string,
): Promise<{ session_id: string; thread_key: string; marked_read: number }> {
  return requestJson(`/api/world/dm/my-threads/${encodeURIComponent(sessionId)}/read/${encodeURIComponent(threadKey)}`, {
    method: "POST",
  });
}

export function getLocationChat(
  location: string,
  since?: string,
  sessionId?: string,
): Promise<{ location: string; messages: LocationChatEntry[] }> {
  const params = new URLSearchParams();
  if (since) params.set("since", since);
  // Identified readers get speaker session/actor ids back; sessionless
  // (public) readers get display names only.
  if (sessionId) params.set("session_id", sessionId);
  const qs = params.toString();
  return requestJson(`/api/world/location/${encodeURIComponent(location)}/chat${qs ? `?${qs}` : ""}`);
}

export type MapMoveResponse = {
  moved: boolean;
  from_location: string;
  to_location: string;
  route: string[];
  route_remaining: string[];
  narrative: string;
};

export function postMapMove(
  sessionId: string,
  destination: string,
  skipToDestination = false,
): Promise<MapMoveResponse> {
  return requestJson<MapMoveResponse>("/api/game/move", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, destination, skip_to_destination: skipToDestination }),
  });
}

export function postLocationChat(
  location: string,
  sessionId: string,
  message: string,
  displayName?: string,
): Promise<{ success: boolean; id: number; ts: string | null }> {
  return requestJson(`/api/world/location/${encodeURIComponent(location)}/chat`, {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      message,
      ...(displayName ? { display_name: displayName } : {}),
    }),
  });
}

export type WorldMapQueryResponse = {
  query: string;
  viewport: {
    north: number;
    south: number;
    east: number;
    west: number;
  };
  occupied_only: boolean;
  quiet_only: boolean;
  include_landmarks: boolean;
  nodes: LocationGraphNode[];
  edges: LocationGraphEdge[];
  count: number;
};

export function queryWorldMap(params: {
  north: number;
  south: number;
  east: number;
  west: number;
  sessionId?: string;
  query?: string;
  occupiedOnly?: boolean;
  quietOnly?: boolean;
  includeLandmarks?: boolean;
}): Promise<WorldMapQueryResponse> {
  const search = new URLSearchParams({
    north: String(params.north),
    south: String(params.south),
    east: String(params.east),
    west: String(params.west),
  });
  if (params.sessionId) search.set("session_id", params.sessionId);
  if (params.query?.trim()) search.set("query", params.query.trim());
  if (params.occupiedOnly) search.set("occupied_only", "true");
  if (params.quietOnly) search.set("quiet_only", "true");
  if (params.includeLandmarks) search.set("include_landmarks", "true");
  return requestJson<WorldMapQueryResponse>(`/api/world/map/query?${search.toString()}`);
}

export type ShadowConsentPayload = {
  session_id: string;
  consent: boolean;
  non_negotiables?: string[];
};

export function postShadowConsent(
  payload: ShadowConsentPayload,
): Promise<{ success: boolean; session_id: string }> {
  return requestJson("/api/world/shadow/consent", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
