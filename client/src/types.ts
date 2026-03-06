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

export type SettingsReadinessResponse = {
  ready: boolean;
  missing: string[];
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

export type SpatialLead = {
  direction: string;
  title: string;
  score: number;
  hint?: string;
};

export type SpatialDirectionTarget = {
  id?: number;
  title?: string;
  text?: string;
  position?: { x: number; y: number };
  accessible?: boolean;
  reason?: string | null;
};

export type SpatialDirectionMap = Record<string, SpatialDirectionTarget | null>;

export type SpatialNavigationResponse = {
  position: { x: number; y: number };
  directions: string[];
  available_directions: SpatialDirectionMap;
  location_storylet?: {
    id: number;
    title: string;
    position: { x: number; y: number };
  } | null;
  leads: SpatialLead[];
  semantic_goal?: string | null;
  goal_hint?: string | null;
};

export type SpatialMoveResponse = {
  result: string;
  new_position: { x: number; y: number };
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

export type ConstellationStorylet = {
  id: number;
  title: string;
  position?: { x: number; y: number } | null;
  score: number;
  accessible: boolean;
  location?: string | null;
  distance?: number | null;
  edges: {
    spatial_neighbors: Record<string, number>;
    semantic_neighbors: number[];
  };
};

export type SemanticConstellationResponse = {
  session_id: string;
  context: {
    location: string;
    vars: VarsRecord;
  };
  storylets: ConstellationStorylet[];
  count: number;
  top_n: number;
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
