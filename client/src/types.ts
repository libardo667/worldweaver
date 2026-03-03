export type VarsRecord = Record<string, unknown>;

export type Choice = {
  label: string;
  set: VarsRecord;
};

export type NextResponse = {
  text: string;
  choices: Choice[];
  vars: VarsRecord;
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
  state_changes: VarsRecord;
  choices: Choice[];
  plausible: boolean;
  vars: VarsRecord;
  triggered_storylet?: string;
};

export type SpatialLead = {
  direction: string;
  title: string;
  score: number;
  hint?: string;
};

export type SpatialNavigationResponse = {
  position: { x: number; y: number };
  directions: string[];
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
