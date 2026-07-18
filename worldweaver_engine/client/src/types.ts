// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

export type VarsRecord = Record<string, unknown>;

export type SessionBootstrapResponse = {
  success: boolean;
  message: string;
  session_id: string;
  vars: VarsRecord;
  theme: string;
  player_role: string;
  bootstrap_state: string;
};

export type ReadinessSeverity = "error" | "warn" | "info";

export type ReadinessCheck = {
  code: string;
  label: string;
  ok: boolean;
  severity: ReadinessSeverity;
  message: string;
};

export type ShardReadinessSummary = {
  shard_id: string;
  city_id: string | null;
  shard_type: string;
  public_url?: string | null;
  federation_url?: string | null;
  demo_key_expires_at?: string | null;
};

export type SettingsReadinessResponse = {
  ready: boolean;
  startup_ready: boolean;
  missing: string[];
  runtime_missing: string[];
  checks: ReadinessCheck[];
  shard: ShardReadinessSummary;
};

export type ResetSessionResponse = {
  success: boolean;
  message: string;
  deleted: VarsRecord;
};

export type DevHardResetResponse = ResetSessionResponse;

export type LeaveSessionResponse = {
  success: boolean;
  message: string;
  session_id: string;
  deleted: VarsRecord;
};

export type V3LaneSource = "world" | "scene" | "player" | "unknown";
export type V3ClarityLevel = "low" | "medium" | "high" | "unknown";

export type ProjectionRefWire = {
  projection_id?: string | null;
  canon_commit_id?: string | null;
  branch_id?: string | null;
};

export type ProjectionRef = {
  projection_id: string | null;
  canon_commit_id: string | null;
  branch_id: string | null;
};

export type V3TurnMetadataWire = {
  lane_source?: string | null;
  clarity_level?: string | null;
  projection_ref?: ProjectionRefWire | null;
};

export type V3TurnMetadata = {
  lane_source: V3LaneSource;
  clarity_level: V3ClarityLevel;
  projection_ref: ProjectionRef | null;
};

export type WorldEvent = {
  id: number;
  session_id?: string | null;
  event_type: string;
  summary: string;
  world_state_delta: VarsRecord;
  created_at?: string | null;
};

export type WorldHistoryResponse = {
  events: WorldEvent[];
  count: number;
};

export type WorldFactsResponse = {
  query: string;
  facts: WorldEvent[];
  count: number;
};


export type StateSummaryResponse = {
  session_id: string;
  variables: VarsRecord;
  inventory: VarsRecord;
  relationships: VarsRecord;
  goal: VarsRecord;
  arc_timeline: VarsRecord[];
  environment: VarsRecord;
  stats: VarsRecord;
};

export type ChangeItem = {
  id: string;
  text: string;
};

export type ToastItem = {
  id: string;
  title: string;
  detail?: string;
  kind: "error" | "info";
};


export type TurnPhase =
  | "idle"
  | "interpreting"
  | "confirming"
  | "rendering"
  | "weaving_ahead";

export type ShardInfo = {
  shard_id: string;
  shard_url: string;
  shard_type: string;
  city_id: string | null;
  last_pulse_ts: string | null;
  status: "healthy" | "degraded" | "stale" | "offline" | string;
};
