// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

// The commons client's read surface. Deliberately narrow: the shard-wide
// telemetry endpoints (digest roster/timeline, rest metrics, roster directory,
// neighborhood vitality) are not wrapped here — the public surface shows the
// place you are looking at, never the whole town's internals.

import type {
  AuthResponse,
  ChatMessage,
  DurableObjectView,
  EntryInfo,
  Grounding,
  GeneratedMapResponse,
  Landmark,
  LocalWorldTraces,
  MakingCatalog,
  MapQueryResult,
  MoveResponse,
  PlaceContext,
  PlacePresence,
  ShardExperience,
  ShardInfo,
  ObjectExchangeCommand,
  ObjectExchanges,
  PendingSpaceAccessRequests,
  SpaceAccessStatus,
  StoopBrowse,
  StoopList,
  TravelDiscovery,
  TravelResponse,
} from "./types";
import { getJwt } from "../session/store";
import { localShardPath } from "./base";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function getJson<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined) qs.set(k, String(v));
  }
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  const resp = await fetch(`${localShardPath(path)}${suffix}`, { headers: { Accept: "application/json" } });
  if (!resp.ok) {
    throw new ApiError(resp.status, `${path} -> ${resp.status}`);
  }
  return (await resp.json()) as T;
}

export function getShardExperience(): Promise<ShardExperience> {
  return getJson("/api/shard/experience");
}

export function getEntry(): Promise<EntryInfo> {
  return getJson("/api/world/entry");
}

export function queryMap(bounds: { north: number; south: number; east: number; west: number }, includeLandmarks = true): Promise<MapQueryResult> {
  return getJson("/api/world/map/query", {
    north: bounds.north,
    south: bounds.south,
    east: bounds.east,
    west: bounds.west,
    include_landmarks: includeLandmarks ? "true" : "false",
  });
}

export function getGeneratedMap(): Promise<GeneratedMapResponse> {
  return getJson("/api/world/map/generated");
}

export function generatedMapSvgUrl(version: string): string {
  const path = localShardPath("/api/world/map/generated.svg");
  return `${path}?v=${encodeURIComponent(version.slice(0, 16))}`;
}

export function getLocationChat(location: string, since?: string, limit = 50): Promise<{ location: string; messages: ChatMessage[] }> {
  return getJson(`/api/world/location/${encodeURIComponent(location)}/chat`, { since, limit });
}

export function getLocationPresence(location: string): Promise<PlacePresence> {
  return getJson(`/api/world/location/${encodeURIComponent(location)}/presence`);
}

export function getPlaceContext(location: string): Promise<PlaceContext> {
  return getJson("/api/world/map/context", { location });
}

export function getNearbyLandmarks(location: string, radiusKm = 0.75): Promise<{ location: string; landmarks: Landmark[] }> {
  return getJson("/api/world/landmarks/nearby", { location, radius_km: radiusKm });
}

export function getGrounding(): Promise<Grounding> {
  return getJson("/api/world/grounding");
}

export function getStoopsAt(location: string): Promise<StoopList> {
  return getJson("/api/world/stoops", { location });
}

export function browseStoopAt(stoopId: string, location: string, sessionId?: string | null): Promise<StoopBrowse> {
  return getJson(
    `/api/world/stoops/${encodeURIComponent(stoopId)}`,
    sessionId ? { session_id: sessionId } : { location },
  );
}

export function getShards(): Promise<{ shards: ShardInfo[] }> {
  return getJson("/ww-world/api/federation/shards");
}

export function getTravelDestinations(): Promise<TravelDiscovery> {
  return getJson("/api/world/travel/destinations");
}

// --- Participant verbs (the join-the-world half) ---------------------------

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", Accept: "application/json" };
  const jwt = getJwt();
  if (jwt) headers.Authorization = `Bearer ${jwt}`;
  const resp = await fetch(localShardPath(path), { method: "POST", headers, body: JSON.stringify(body) });
  if (!resp.ok) {
    let detail = "";
    try {
      const payload = await resp.json();
      detail = typeof payload?.detail === "string" ? payload.detail : JSON.stringify(payload?.detail ?? "");
    } catch {
      // Leave the status alone.
    }
    throw new ApiError(resp.status, detail || `${path} -> ${resp.status}`);
  }
  return (await resp.json()) as T;
}

async function patchJson<T>(path: string, body: unknown): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", Accept: "application/json" };
  const jwt = getJwt();
  if (jwt) headers.Authorization = `Bearer ${jwt}`;
  const resp = await fetch(localShardPath(path), { method: "PATCH", headers, body: JSON.stringify(body) });
  if (!resp.ok) {
    let detail = "";
    try {
      const payload = await resp.json();
      detail = typeof payload?.detail === "string" ? payload.detail : JSON.stringify(payload?.detail ?? "");
    } catch {
      // Leave the status alone.
    }
    throw new ApiError(resp.status, detail || `${path} -> ${resp.status}`);
  }
  return (await resp.json()) as T;
}

export function getTerms(): Promise<{ terms: string }> {
  return getJson("/api/auth/terms");
}

export function postRegister(input: { email: string; password: string; password_confirmation: string; terms_accepted: boolean }): Promise<AuthResponse> {
  return postJson("/api/auth/register", { ...input, pass_type: "citizen" });
}

export function postLogin(identifier: string, password: string): Promise<AuthResponse> {
  return postJson("/api/auth/login", { identifier, password });
}

export function patchProfile(displayName: string): Promise<AuthResponse> {
  return patchJson("/api/auth/profile", { display_name: displayName });
}

export function postRequestPasswordReset(identifier: string): Promise<{ ok: boolean }> {
  return postJson("/api/auth/request-password-reset", { identifier });
}

export function postResetPassword(token: string, newPassword: string): Promise<AuthResponse> {
  return postJson("/api/auth/reset-password", { token, new_password: newPassword });
}

export function postVerifyEmail(token: string): Promise<AuthResponse> {
  return postJson("/api/auth/verify-email", { token });
}

export function postResendVerification(): Promise<{ ok: boolean; sent: boolean; retry_later: boolean; already_verified: boolean }> {
  return postJson("/api/auth/resend-verification", {});
}

export function postSessionBootstrap(sessionId: string, worldId: string, playerRole: string, entryLocation: string): Promise<{ success: boolean; session_id: string }> {
  return postJson("/api/session/bootstrap", {
    session_id: sessionId,
    world_id: worldId,
    player_role: playerRole,
    entry_location: entryLocation,
    bootstrap_source: "commons_client",
  });
}

export function postMove(sessionId: string, destination: string): Promise<MoveResponse> {
  return postJson("/api/game/move", { session_id: sessionId, destination, skip_to_destination: false });
}

export function postSpeak(location: string, sessionId: string, displayName: string, message: string): Promise<{ success: boolean }> {
  return postJson(`/api/world/location/${encodeURIComponent(location)}/chat`, {
    session_id: sessionId,
    display_name: displayName,
    message,
  });
}

export function getWorldTraces(sessionId: string): Promise<LocalWorldTraces> {
  return getJson("/api/world/traces", { session_id: sessionId });
}

export function postWorldTrace(sessionId: string, body: string, target = ""): Promise<{ ok: boolean }> {
  return postJson("/api/world/traces", { session_id: sessionId, body, target });
}

export function postLeaveSession(sessionId: string): Promise<{ success?: boolean }> {
  return postJson("/api/session/leave", { session_id: sessionId });
}

export function postTravelDeparture(
  sessionId: string,
  routeId: string,
  destinationShard: string,
  travelId: string,
): Promise<TravelResponse> {
  return postJson("/api/session/travel/depart", {
    session_id: sessionId,
    route_id: routeId,
    destination_shard: destinationShard,
    travel_id: travelId,
  });
}

export function postRetryTravelDeparture(travelId: string): Promise<TravelResponse> {
  return postJson(`/api/session/travel/${encodeURIComponent(travelId)}/retry-departure`, {});
}

export function postTravelArrival(travelId: string, sessionId: string): Promise<TravelResponse> {
  return postJson("/api/session/travel/arrive", { travel_id: travelId, session_id: sessionId });
}

export function postRetryTravelArrival(travelId: string): Promise<TravelResponse> {
  return postJson(`/api/session/travel/${encodeURIComponent(travelId)}/retry-arrival`, {});
}

export function postTakeStoopEntry(entryId: string, sessionId: string): Promise<{ replayed?: boolean }> {
  return postJson(`/api/world/stoops/entries/${encodeURIComponent(entryId)}/take`, {
    session_id: sessionId,
    idempotency_key: `take-${entryId}-${sessionId}`,
  });
}

export function postWithdrawStoopEntry(entryId: string, sessionId: string): Promise<{ replayed?: boolean }> {
  return postJson(`/api/world/stoops/entries/${encodeURIComponent(entryId)}/withdraw`, {
    session_id: sessionId,
    idempotency_key: freshKey("stoopwithdraw"),
  });
}

function freshKey(verb: string): string {
  return `${verb}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function getMakingCatalog(sessionId: string): Promise<MakingCatalog> {
  return getJson("/api/world/making", { session_id: sessionId });
}

export function postMake(sessionId: string, recipeId: string): Promise<{ object?: { object_id: string } }> {
  return postJson("/api/world/make", {
    session_id: sessionId,
    recipe_id: recipeId,
    idempotency_key: freshKey("make"),
  });
}

export function getMyObjects(sessionId: string): Promise<{ objects: DurableObjectView[]; count: number }> {
  return getJson("/api/world/objects", { session_id: sessionId });
}

export function postPickUpObject(objectId: string, sessionId: string): Promise<unknown> {
  return postJson(`/api/world/objects/${encodeURIComponent(objectId)}/pick-up`, {
    session_id: sessionId,
    idempotency_key: freshKey("pickup"),
  });
}

export function postPutDownObject(objectId: string, sessionId: string): Promise<unknown> {
  return postJson(`/api/world/objects/${encodeURIComponent(objectId)}/place`, {
    session_id: sessionId,
    idempotency_key: freshKey("place"),
  });
}

export function postLeaveOnStoop(stoopId: string, objectId: string, sessionId: string): Promise<unknown> {
  return postJson(`/api/world/stoops/${encodeURIComponent(stoopId)}/leave`, {
    session_id: sessionId,
    object_id: objectId,
    idempotency_key: freshKey("stoopleave"),
  });
}

export function getObjectExchanges(sessionId: string): Promise<ObjectExchanges> {
  return getJson("/api/world/exchanges", { session_id: sessionId });
}

export function postGiveObject(objectId: string, sessionId: string, recipientSessionId: string): Promise<unknown> {
  return postJson(`/api/world/objects/${encodeURIComponent(objectId)}/give`, {
    session_id: sessionId,
    recipient_session_id: recipientSessionId,
    idempotency_key: freshKey("give"),
  });
}

export function postExchangeOffer(
  sessionId: string,
  recipientSessionId: string,
  offeredObjectId: string,
  requestedObjectId: string,
): Promise<ObjectExchangeCommand> {
  return postJson("/api/world/exchanges", {
    session_id: sessionId,
    recipient_session_id: recipientSessionId,
    offered_object_id: offeredObjectId,
    requested_object_id: requestedObjectId,
    idempotency_key: freshKey("exchange-offer"),
  });
}

export function postExchangeDecision(
  exchangeId: string,
  sessionId: string,
  decision: "accept" | "decline" | "cancel",
): Promise<ObjectExchangeCommand> {
  return postJson(`/api/world/exchanges/${encodeURIComponent(exchangeId)}/${decision}`, {
    session_id: sessionId,
    idempotency_key: freshKey(`exchange-${decision}`),
  });
}

// --- One exact doorway ----------------------------------------------------

export function getSpaceAccess(sessionId: string, location: string): Promise<{ access: SpaceAccessStatus }> {
  return getJson("/api/world/access", { session_id: sessionId, location });
}

export function getPendingSpaceAccessRequests(
  sessionId: string,
  location: string,
): Promise<PendingSpaceAccessRequests> {
  return getJson("/api/world/access/requests", { session_id: sessionId, location });
}

export function postSpaceAccessRequest(sessionId: string, location: string, note: string): Promise<unknown> {
  return postJson("/api/world/access/requests", {
    session_id: sessionId,
    location,
    note,
    idempotency_key: freshKey("access-request"),
  });
}

export function postResolveSpaceAccessRequest(
  requestId: string,
  sessionId: string,
  decision: "admitted" | "denied",
): Promise<unknown> {
  return postJson(`/api/world/access/requests/${encodeURIComponent(requestId)}/resolve`, {
    session_id: sessionId,
    decision,
    idempotency_key: freshKey(`access-${decision}`),
  });
}

export function postSpaceMode(
  sessionId: string,
  location: string,
  mode: "public" | "requestable" | "private" | "closed",
  note: string,
): Promise<unknown> {
  return postJson("/api/world/access/mode", {
    session_id: sessionId,
    location,
    mode,
    note,
    idempotency_key: freshKey("access-mode"),
  });
}
