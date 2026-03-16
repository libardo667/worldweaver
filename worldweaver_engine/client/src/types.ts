export type VarsRecord = Record<string, unknown>;

export type Choice = {
  label: string;
  set: VarsRecord;
};

export type NextResponse = {
  text: string;
  choices: Choice[];
  vars: VarsRecord;
  v3?: V3TurnMetadataWire | null;
  lane_source?: string | null;
  clarity_level?: string | null;
  projection_ref?: ProjectionRefWire | null;
};

export type SessionBootstrapResponse = {
  success: boolean;
  message: string;
  session_id: string;
  vars: VarsRecord;
  storylets_created: number;
  theme: string;
  player_role: string;
  bootstrap_state: string;
};

export type ModelSummary = {
  model_id: string;
  label: string;
  tier: string;
  creative_quality: number;
  context_window: number;
  estimated_10_turn_cost_usd: number;
  notes: string;
};

export type EstimatedSessionCost = {
  model: string;
  label: string;
  tier: string;
  creative_quality: number;
  turns: number;
  input_tokens: number;
  output_tokens: number;
  input_cost_usd: number;
  output_cost_usd: number;
  total_cost_usd: number;
  notes: string;
};

export type CurrentModelResponse = {
  model_id: string;
  label: string;
  tier: string;
  creative_quality: number;
  context_window: number;
  ai_enabled: boolean;
  api_key_configured: boolean;
  estimated_session_cost: EstimatedSessionCost;
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

export type ApiKeyUpdateRequest = {
  api_key: string;
};

export type ModelSwitchResponse = {
  success: boolean;
  previous_model: string;
  current_model: string;
  label: string;
  tier: string;
  estimated_10_turn_cost_usd: number;
  message: string;
};

export type ResetSessionResponse = {
  success: boolean;
  message: string;
  storylets_seeded: number;
  legacy_seed_mode: boolean;
  deleted: VarsRecord;
};

export type DevHardResetResponse = ResetSessionResponse;

export type LeaveSessionResponse = {
  success: boolean;
  message: string;
  session_id: string;
  deleted: VarsRecord;
};

export type ActionResponse = {
  narrative: string;
  ack_line?: string;
  state_changes: VarsRecord;
  choices: Choice[];
  plausible: boolean;
  vars: VarsRecord;
  triggered_storylet?: string;
  v3?: V3TurnMetadataWire | null;
  lane_source?: string | null;
  clarity_level?: string | null;
  projection_ref?: ProjectionRefWire | null;
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
  storylet_id?: number | null;
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

export type PrefetchTriggerResponse = {
  triggered: boolean;
};

export type PrefetchBudgetMetadata = {
  budget_ms: number;
  max_nodes: number;
  expansion_depth: number;
};

export type PrefetchStatusResponse = {
  stubs_cached: number;
  expires_in_seconds: number;
  budget_ms?: number | null;
  max_nodes?: number | null;
  expansion_depth?: number | null;
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
