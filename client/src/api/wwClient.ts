import type {
  ActionResponse,
  CurrentModelResponse,
  DevHardResetResponse,
  ModelSummary,
  ModelSwitchResponse,
  NextResponse,
  PrefetchStatusResponse,
  PrefetchTriggerResponse,
  ResetSessionResponse,
  SpatialMoveResponse,
  SpatialNavigationResponse,
  SemanticConstellationResponse,
  StateSummaryResponse,
  VarsRecord,
  WorldFactsResponse,
  WorldHistoryResponse,
  SettingsReadinessResponse,
} from "../types";
import { getJwt } from "../state/sessionStore";

const API_BASE = (import.meta.env.VITE_WW_API_BASE as string | undefined) ?? "";

async function requestJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const jwt = getJwt();
  const authHeader: Record<string, string> = jwt ? { Authorization: `Bearer ${jwt}` } : {};
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...authHeader,
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export type AuthResponse = {
  token: string;
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


export function getSpatialNavigation(
  sessionId: string,
): Promise<SpatialNavigationResponse> {
  return requestJson<SpatialNavigationResponse>(
    `/api/spatial/navigation/${encodeURIComponent(sessionId)}`,
  );
}

export function postSpatialMove(
  sessionId: string,
  direction: string,
): Promise<SpatialMoveResponse> {
  return requestJson<SpatialMoveResponse>(
    `/api/spatial/move/${encodeURIComponent(sessionId)}`,
    {
      method: "POST",
      body: JSON.stringify({ direction }),
    },
  );
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

export function getSemanticConstellation(
  sessionId: string,
  topN = 20,
): Promise<SemanticConstellationResponse> {
  const params = new URLSearchParams({
    top_n: String(topN),
  });
  return requestJson<SemanticConstellationResponse>(
    `/api/semantic/constellation/${encodeURIComponent(sessionId)}?${params.toString()}`,
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
  count: number;
  agent_count?: number;
  is_player: boolean;
  lat?: number | null;
  lon?: number | null;
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
  player_location: string | null;
  location_chat?: LocationChatEntry[];
};

export function getWorldDigest(sessionId?: string, eventsLimit = 20): Promise<WorldDigestResponse> {
  const params = new URLSearchParams({ events_limit: String(eventsLimit) });
  if (sessionId) params.set("session_id", sessionId);
  return requestJson<WorldDigestResponse>(`/api/world/digest?${params.toString()}`);
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

export async function streamAction(
  sessionId: string,
  action: string,
  vars?: VarsRecord,
  onDraftChunk?: (text: string) => void,
  signal?: AbortSignal,
  onAckLine?: (text: string) => void,
): Promise<ActionResponse> {
  const _streamJwt = getJwt();
  const response = await fetch(`${API_BASE}/api/action/stream`, {
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
    throw new Error(body || `Request failed with status ${response.status}`);
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
}

export function postLetter(
  toAgent: string,
  fromName: string,
  body: string,
  sessionId?: string,
): Promise<{ success: boolean; letter_id: string; delivered_to: string }> {
  return requestJson("/api/world/letter", {
    method: "POST",
    body: JSON.stringify({
      to_agent: toAgent,
      from_name: fromName,
      body,
      ...(sessionId ? { session_id: sessionId } : {}),
    }),
  });
}

export type InboxLetter = { filename: string; body: string };

export function getAgentInbox(
  agent: string,
): Promise<{ agent: string; letters: InboxLetter[]; count: number }> {
  return requestJson(`/api/world/letters/inbox/${encodeURIComponent(agent)}`);
}

export function getPlayerInbox(
  sessionId: string,
): Promise<{ session_id: string; letters: InboxLetter[]; count: number }> {
  return requestJson(`/api/world/letters/my-inbox/${encodeURIComponent(sessionId)}`);
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
): Promise<MapMoveResponse> {
  return requestJson<MapMoveResponse>("/api/game/move", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, destination }),
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
