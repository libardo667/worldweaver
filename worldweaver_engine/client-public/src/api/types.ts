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

export type MapEdge = { from: string; to: string };

export type MapQueryResult = { nodes: MapNode[]; edges: MapEdge[] };

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
};

export type AuthResponse = {
  token: string;
  actor_id: string;
  player_id: string;
  username: string;
  display_name: string;
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
  shard_type: string;
  city_id: string;
  status: "healthy" | "degraded" | "stale" | "offline" | string;
};
