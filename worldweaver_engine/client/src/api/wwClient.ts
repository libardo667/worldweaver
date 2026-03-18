import type {
  ActionResponse,
  CurrentModelResponse,
  DevHardResetResponse,
  LeaveSessionResponse,
  ModelSummary,
  ModelSwitchResponse,
  NextResponse,
  PrefetchStatusResponse,
  PrefetchTriggerResponse,
  ResetSessionResponse,
  StateSummaryResponse,
  VarsRecord,
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
const _enableActionStream = String(import.meta.env.VITE_ENABLE_ACTION_STREAM ?? "").trim() === "1";

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

export async function fetchShards(): Promise<ShardInfo[]> {
  try {
    // Use the Vite proxy path so this stays same-origin on HTTPS (world-weaver.org).
    // Vite rewrites /ww-world/* → VITE_WW_WORLD_URL/* server-side.
    const resp = await fetch(`/ww-world/api/federation/shards`);
    if (!resp.ok) return [];
    const data = await resp.json() as { shards: ShardInfo[] };
    return data.shards ?? [];
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

export function postLogin(username: string, password: string): Promise<AuthResponse> {
  return requestJson<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function getAuthMe(): Promise<AuthResponse> {
  return requestJson<AuthResponse>("/api/auth/me");
}

export function postNext(
  sessionId: string,
  vars: VarsRecord,
  choiceTaken?: any,
): Promise<NextResponse> {
  return requestJson<NextResponse>("/api/next", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      vars,
      ...(choiceTaken ? { choice_taken: choiceTaken } : {}),
    }),
  });
}

export function postAction(
  sessionId: string,
  action: string,
  opts?: {
    vars?: VarsRecord;
    choiceLabel?: string;
    choiceVars?: Record<string, unknown>;
  },
): Promise<ActionResponse> {
  return requestJson<ActionResponse>("/api/action", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      action,
      ...(opts?.vars ? { vars: opts.vars } : {}),
      ...(opts?.choiceLabel ? { choice_label: opts.choiceLabel } : {}),
      ...(opts?.choiceVars ? { choice_vars: opts.choiceVars } : {}),
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

export function getStateSummary(sessionId: string): Promise<StateSummaryResponse> {
  return requestJson<StateSummaryResponse>(
    `/api/state/${encodeURIComponent(sessionId)}`,
  );
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

export function postPrefetchFrontier(
  sessionId: string,
): Promise<PrefetchTriggerResponse> {
  return requestJson<PrefetchTriggerResponse>("/api/prefetch/frontier", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export function getPrefetchStatus(
  sessionId: string,
): Promise<PrefetchStatusResponse> {
  return requestJson<PrefetchStatusResponse>(
    `/api/prefetch/status/${encodeURIComponent(sessionId)}`,
  );
}


export function getAvailableModels(): Promise<ModelSummary[]> {
  return requestJson<ModelSummary[]>("/api/models");
}

export function getCurrentModel(): Promise<CurrentModelResponse> {
  return requestJson<CurrentModelResponse>("/api/model");
}

export function putCurrentModel(modelId: string): Promise<ModelSwitchResponse> {
  return requestJson<ModelSwitchResponse>("/api/model", {
    method: "PUT",
    body: JSON.stringify({ model_id: modelId }),
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
  rest_config: {
    residents_dir: string;
    residents_dir_exists: boolean;
    defaults: {
      enabled: boolean;
      break_minutes: number;
      sleep_hours: number;
      sync_seconds: number;
      confirmations_required: number;
      confirmation_window_minutes: number;
      wake_grace_minutes: number;
    };
    resident_count: number;
    override_count: number;
    overrides: Array<Record<string, unknown> & { resident: string }>;
    load_errors: string[];
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

export function postSettingsKey(apiKey: string): Promise<{ success: boolean; message: string }> {
  return requestJson<{ success: boolean; message: string }>("/api/settings/key", {
    method: "POST",
    body: JSON.stringify({ api_key: apiKey }),
  });
}

function parseSseBlock(
  block: string,
): { event: string; data: string } | null {
  const lines = block
    .split("\n")
    .map((line) => line.trimEnd())
    .filter((line) => line.length > 0);
  if (lines.length === 0) {
    return null;
  }

  let event = "message";
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }

  if (dataLines.length === 0) {
    return null;
  }
  return { event, data: dataLines.join("\n") };
}

function buildQuickAckLine(action: string): string {
  const cleaned = String(action || "").trim().replace(/\s+/g, " ");
  const shortened = cleaned.length > 110 ? `${cleaned.slice(0, 107)}...` : cleaned;
  return `You commit to: "${shortened}".`;
}

async function fallbackToNonStreamingAction(
  sessionId: string,
  action: string,
  vars: VarsRecord | undefined,
  onAckLine?: (text: string) => void,
): Promise<ActionResponse> {
  if (onAckLine) {
    onAckLine(buildQuickAckLine(action));
  }
  return postAction(sessionId, action, vars ? { vars } : undefined);
}

export async function streamAction(
  sessionId: string,
  action: string,
  vars?: VarsRecord,
  onDraftChunk?: (text: string) => void,
  signal?: AbortSignal,
  onAckLine?: (text: string) => void,
): Promise<ActionResponse> {
  if (!_enableActionStream) {
    return fallbackToNonStreamingAction(sessionId, action, vars, onAckLine);
  }
  try {
    const _streamJwt = getJwt();
    const response = await fetch(`${getEffectiveApiBase()}/api/action/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...(_streamJwt ? { Authorization: `Bearer ${_streamJwt}` } : {}),
      },
      body: JSON.stringify({
        session_id: sessionId,
        action,
        ...(vars ? { vars } : {}),
      }),
      signal,
    });

    if (!response.ok) {
      const body = await response.text();
      throw buildApiRequestError(response.status, body);
    }
    if (!response.body) {
      throw new Error("Streaming response body was not available.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalPayload: ActionResponse | null = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

      let sep = buffer.indexOf("\n\n");
      while (sep !== -1) {
        const raw = buffer.slice(0, sep).trim();
        buffer = buffer.slice(sep + 2);
        if (raw) {
          const parsed = parseSseBlock(raw);
          if (parsed) {
            if (parsed.event === "phase:ack") {
              const payload = JSON.parse(parsed.data) as { ack_line?: string };
              if (typeof payload.ack_line === "string" && onAckLine) {
                onAckLine(payload.ack_line);
              }
            } else if (parsed.event === "draft_chunk") {
              const payload = JSON.parse(parsed.data) as { text?: string };
              if (typeof payload.text === "string" && onDraftChunk) {
                onDraftChunk(payload.text);
              }
            } else if (parsed.event === "final") {
              finalPayload = JSON.parse(parsed.data) as ActionResponse;
            } else if (parsed.event === "error") {
              const payload = JSON.parse(parsed.data) as { detail?: string };
              throw new Error(payload.detail || "Action stream failed.");
            }
          }
        }
        sep = buffer.indexOf("\n\n");
      }
    }

    if (finalPayload) {
      return finalPayload;
    }
    throw new Error("Action stream ended before final payload.");
  } catch (error) {
    if ((error as { name?: string })?.name === "AbortError") {
      throw error;
    }
    if (isApiRequestError(error)) {
      throw error;
    }
    return fallbackToNonStreamingAction(sessionId, action, vars, onAckLine);
  }
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
): Promise<{ location: string; messages: LocationChatEntry[] }> {
  const params = new URLSearchParams();
  if (since) params.set("since", since);
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
