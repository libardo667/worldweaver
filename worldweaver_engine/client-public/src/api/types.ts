// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

export type MapNode = {
  key: string;
  name: string;
  node_type: string;
  count: number;
  agent_count: number;
  present_count: number;
  present_names: string[];
  player_names: string[];
  agent_names: string[];
  is_player: boolean;
  lat: number | null;
  lon: number | null;
  description: string;
  parent_location: string;
};

export type MapEdge = { from: string; to: string; kind: "path" | "contains" | string };

export type MapQueryResult = { nodes: MapNode[]; edges: MapEdge[] };

export type GeneratedMapArtifact = {
  schema_version: string;
  artifact_sha256: string;
  bounds: { north: number; south: number; east: number; west: number };
  grid: { width: number; height: number; section_size: number };
  generator: { id: string; version: string; seed: string };
  svg: { filename: string; sha256: string };
  section_count: number;
};

export type GeneratedMapResponse = {
  available: boolean;
  city_id: string;
  artifact: GeneratedMapArtifact | null;
};

export type PlacePresence = {
  location: string;
  present_count: number;
  present_names: string[];
};

/** Public chat shape: sessionless readers get no speaker session/actor ids. */
export type ChatMessage = {
  id: number;
  display_name: string | null;
  message: string;
  ts: string | null;
};

export type Grounding = {
  city: string;
  city_id: string;
  fictional: boolean;
  timezone: string;
  datetime_str: string;
  day_of_week: string;
  time_of_day: "morning" | "afternoon" | "evening" | "night" | string;
  season: string;
  hour: number;
  month: number;
  weather: string;
  temperature_f: number | null;
  weather_description: string;
};

export type EntryDisclosure = {
  title: string;
  summary: string;
  capabilities?: { id: string; title: string; description: string }[];
  enabled_stakes?: string[];
  disabled_stakes?: string[];
};

export type ShardExperience = {
  shard_id: string;
  shard_type: string;
  experience_type: string;
  game_rules_active: boolean;
  ruleset?: { id: string; version: string };
  entry_disclosure?: EntryDisclosure;
};

export type EntryNode = { name: string; key: string; lat: number | null; lon: number | null };

export type EntryInfo = {
  world_id: string;
  snapshot: string;
  fictional: boolean;
  map_style: "schematic" | "geographic";
  locations: string[];
  entry_nodes: EntryNode[];
};

export type CurrentSession = {
  active: boolean;
  session_id: string | null;
  location: string | null;
};

export type PlaceContext = {
  location: string;
  city_id: string;
  context: string;
  available: boolean;
};

export type Landmark = {
  name: string;
  lat: number | null;
  lon: number | null;
  distance_km?: number;
  description?: string;
};

export type StoopShell = {
  stoop_id: string;
  title: string;
  prompt: string;
  location: string;
  capacity: number;
  active_count: number;
  space_remaining: number;
};

export type StoopObjectView = {
  object_id: string;
  name: string;
  description: string;
  object_kind?: string;
  provenance?: Record<string, unknown>;
};

export type StoopEntry = {
  entry_id: string;
  stoop_id: string;
  status: string;
  object: StoopObjectView;
  created_at: string | null;
  can_take?: boolean;
  can_withdraw?: boolean;
};

export type StoopBrowse = {
  stoop: StoopShell;
  entries: StoopEntry[];
  count: number;
};

export type StoopList = { location: string; stoops: StoopShell[]; count: number };

export type MakingMaterial = {
  material_id: string;
  title?: string;
  available_units: number;
};

export type MakingRecipe = {
  recipe_id: string;
  title: string;
  description: string;
  inputs: Record<string, number>;
  output: { name?: string; description?: string; object_kind?: string };
  can_make: boolean;
  missing_units: Record<string, number>;
};

export type MakingCatalog = {
  location: string;
  materials: MakingMaterial[];
  recipes: MakingRecipe[];
};

export type DurableObjectView = {
  object_id: string;
  name: string;
  description: string;
  object_kind: string;
  status: string;
  attachment: { kind: "custody"; actor_id: string } | { kind: "place"; location: string };
  relation: "carried" | "here";
  can_pick_up: boolean;
};

export type WorldTrace = {
  trace_id: string;
  author_name: string;
  location: string;
  target: string;
  body: string;
  created_at: string | null;
  expires_at: string | null;
};

export type LocalWorldTraces = {
  location: string;
  traces: WorldTrace[];
  count: number;
};

export type ObjectExchange = {
  exchange_id: string;
  status: "open" | "completed" | "declined" | "cancelled" | string;
  proposer_actor_id: string;
  recipient_actor_id: string;
  offered_object: DurableObjectView;
  requested_object: DurableObjectView;
  viewer_role: "proposer" | "recipient" | "observer";
  counterpart_present: boolean;
  can_accept: boolean;
  can_decline: boolean;
  can_cancel: boolean;
};

export type ObjectExchangeOfferOption = {
  recipient_actor_id: string;
  recipient_session_id: string;
  requested_objects: DurableObjectView[];
};

export type ObjectExchanges = {
  exchanges: ObjectExchange[];
  count: number;
  offer_options: ObjectExchangeOfferOption[];
};

export type ObjectExchangeCommand = {
  ok: boolean;
  replayed: boolean;
  exchange: ObjectExchange;
  receipt: { receipt_id: string; operation: string; exchange_id: string };
};

export type SpaceAccessStatus = {
  location: string;
  mode: "public" | "requestable" | "private" | "closed" | string;
  note: string;
  revision: number;
  is_controller: boolean;
  admitted: boolean;
  can_enter: boolean;
  can_request: boolean;
  entry_reason: string;
  request_pending: boolean;
  active_grants: { actor_id: string; session_id: string }[];
};

export type SpaceAccessRequest = {
  request_id: string;
  requester_actor_id: string;
  requester_session_id: string;
  note: string;
  status: string;
  created_at: string | null;
};

export type PendingSpaceAccessRequests = {
  location: string;
  requests: SpaceAccessRequest[];
  count: number;
};

export type AuthResponse = {
  token: string;
  actor_id: string;
  player_id: string;
  username: string;
  email: string;
  display_name: string;
  profile_complete: boolean;
  email_verified: boolean;
  email_verification_required: boolean;
};

export type MoveResponse = {
  moved: boolean;
  from_location: string;
  to_location: string;
  route: string[];
  route_remaining: string[];
  narrative: string;
};

export type ShardInfo = {
  shard_id: string;
  shard_url: string;
  client_url?: string | null;
  shard_type: string;
  city_id: string;
  status: "healthy" | "degraded" | "stale" | "offline" | string;
};

export type TravelNode = {
  shard_id: string;
  shard_url: string;
  client_url?: string | null;
  status: string;
};

export type TravelRoute = {
  route_id: string;
  from_city_id: string;
  to_city_id: string;
  mode: string;
  operator: string;
  duration_hours: number | null;
  departure_hub_id: string;
  departure_hub: string;
  departure_place: string;
  arrival_hub_id: string;
  arrival_hub: string;
  notes: string;
  availability: "available" | "unhosted" | "offline" | "unknown" | string;
  nodes: TravelNode[];
};

export type TravelDiscovery = {
  source: { shard_id: string; city_id: string };
  registry: { configured: boolean; reachable: boolean };
  destinations: TravelRoute[];
};

export type TravelHandoff = {
  travel_id: string;
  actor_id: string;
  session_id: string;
  source_shard: string;
  destination_shard: string;
  destination_client_url?: string | null;
  route_id?: string | null;
  departure_hub?: string | null;
  arrival_hub?: string | null;
  status: string;
  last_error?: string | null;
};

export type TravelResponse = {
  success: boolean;
  recoverable?: boolean;
  message?: string;
  place?: string | null;
  handoff: TravelHandoff;
};
