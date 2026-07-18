// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

// The commons client's read surface. Deliberately narrow: the shard-wide
// telemetry endpoints (digest roster/timeline, rest metrics, roster directory,
// neighborhood vitality) are not wrapped here — the public surface shows the
// place you are looking at, never the whole town's internals.

import type {
  ChatMessage,
  EntryInfo,
  Grounding,
  Landmark,
  MapQueryResult,
  PlaceContext,
  ShardExperience,
  ShardInfo,
  StoopBrowse,
  StoopList,
} from "./types";

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
  const resp = await fetch(`${path}${suffix}`, { headers: { Accept: "application/json" } });
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

export function getLocationChat(location: string, since?: string, limit = 50): Promise<{ location: string; messages: ChatMessage[] }> {
  return getJson(`/api/world/location/${encodeURIComponent(location)}/chat`, { since, limit });
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

export function browseStoopAt(stoopId: string, location: string): Promise<StoopBrowse> {
  return getJson(`/api/world/stoops/${encodeURIComponent(stoopId)}`, { location });
}

export function getShards(): Promise<{ shards: ShardInfo[] }> {
  return getJson("/ww-world/api/federation/shards");
}
