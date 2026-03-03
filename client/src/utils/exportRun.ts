import packageJson from "../../package.json";
import type { VarsRecord, WorldEvent } from "../types";

export type ExportableEvent = {
  id: number;
  session_id?: string | null;
  storylet_id?: number | null;
  event_type: string;
  summary: string;
  world_state_delta: VarsRecord;
  created_at?: string | null;
};

export type RunExportBundle = {
  export_schema_version: "worldweaver.run.v1";
  chronicle_schema_version: "worldweaver.chronicle.v1";
  client_version: string;
  session_id: string;
  generated_at: string;
  history_count: number;
  pinned_count: number;
  turning_points_count: number;
  vars_snapshot: VarsRecord;
  recent_history: ExportableEvent[];
  pinned_items: ExportableEvent[];
  key_turning_points: ExportableEvent[];
};

const RUN_EXPORT_SCHEMA_VERSION = "worldweaver.run.v1" as const;
const CHRONICLE_SCHEMA_VERSION = "worldweaver.chronicle.v1" as const;
const MAX_HISTORY_EXPORT = 120;
const CLIENT_VERSION = String((packageJson as { version?: string }).version ?? "0.0.0");
const REDACT_KEY_PATTERNS = [/embedding/i, /prompt/i];

function toTimestamp(value?: string | null): number {
  if (!value) {
    return 0;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function shouldRedactKey(key: string): boolean {
  if (key.startsWith("__")) {
    return true;
  }
  return REDACT_KEY_PATTERNS.some((pattern) => pattern.test(key));
}

function sanitizeValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeValue(item));
  }
  if (!value || typeof value !== "object") {
    return value;
  }
  const source = value as Record<string, unknown>;
  const out: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(source)) {
    if (shouldRedactKey(key)) {
      continue;
    }
    out[key] = sanitizeValue(item);
  }
  return out;
}

function sanitizeVars(input: VarsRecord | undefined): VarsRecord {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    return {};
  }
  return sanitizeValue(input) as VarsRecord;
}

function sanitizeEvent(event: WorldEvent): ExportableEvent {
  return {
    id: Number(event.id),
    session_id: event.session_id ?? null,
    storylet_id: event.storylet_id ?? null,
    event_type: String(event.event_type),
    summary: String(event.summary),
    world_state_delta: sanitizeVars(event.world_state_delta),
    created_at: event.created_at ?? null,
  };
}

function hasWorldDelta(delta: VarsRecord | undefined): boolean {
  if (!delta || typeof delta !== "object" || Array.isArray(delta)) {
    return false;
  }
  return Object.keys(delta).length > 0;
}

function formatDateTime(value?: string | null): string {
  if (!value) {
    return "unknown";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "unknown";
  }
  return parsed.toLocaleString();
}

function stableEventRank(events: WorldEvent[]): WorldEvent[] {
  return [...events].sort((a, b) => {
    const scoreA =
      (a.event_type === "permanent_change" ? 100 : 0) +
      (hasWorldDelta(a.world_state_delta) ? 30 : 0);
    const scoreB =
      (b.event_type === "permanent_change" ? 100 : 0) +
      (hasWorldDelta(b.world_state_delta) ? 30 : 0);
    if (scoreA !== scoreB) {
      return scoreB - scoreA;
    }

    const timeA = toTimestamp(a.created_at);
    const timeB = toTimestamp(b.created_at);
    if (timeA !== timeB) {
      return timeB - timeA;
    }

    return b.id - a.id;
  });
}

export function selectBecauseOfEvents(events: WorldEvent[], maxItems = 5): WorldEvent[] {
  if (events.length === 0) {
    return [];
  }
  const ranked = stableEventRank(events);
  const count = Math.min(maxItems, ranked.length);
  return ranked.slice(0, count);
}

function downloadTextFile(filename: string, content: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function buildMarkdown(
  sessionId: string,
  varsSnapshot: VarsRecord,
  events: ExportableEvent[],
  becauseOf: ExportableEvent[],
  pinned: ExportableEvent[],
): string {
  const playerName = typeof varsSnapshot.name === "string" ? varsSnapshot.name : "Traveler";
  const location = typeof varsSnapshot.location === "string" ? varsSnapshot.location : "unknown";
  const lines: string[] = [];
  lines.push(`# Chronicle`);
  lines.push("");
  lines.push(`Schema: \`${CHRONICLE_SCHEMA_VERSION}\``);
  lines.push(`Client: \`${CLIENT_VERSION}\``);
  lines.push(`- Session: \`${sessionId}\``);
  lines.push(`- Generated: ${new Date().toLocaleString()}`);
  lines.push(`- Perspective: ${playerName} @ ${location}`);
  lines.push(`- Recent history events: ${events.length}`);
  lines.push(`- Pinned items: ${pinned.length}`);
  lines.push("");
  lines.push("## Key Turning Points");
  lines.push("");
  if (becauseOf.length === 0) {
    lines.push("- No high-salience events yet.");
  } else {
    for (const event of becauseOf) {
      lines.push(`- **${event.event_type}** (${formatDateTime(event.created_at)}): ${event.summary}`);
    }
  }
  lines.push("");
  lines.push("## Pinned");
  lines.push("");
  if (pinned.length === 0) {
    lines.push("- No pinned events.");
  } else {
    for (const event of pinned) {
      lines.push(`- **${event.event_type}** (${formatDateTime(event.created_at)}): ${event.summary}`);
    }
  }
  lines.push("");
  lines.push("## Timeline");
  lines.push("");
  if (events.length === 0) {
    lines.push("- No world history recorded yet.");
  } else {
    for (const event of events) {
      lines.push(`- **${event.event_type}** (${formatDateTime(event.created_at)}): ${event.summary}`);
    }
  }
  lines.push("");
  return lines.join("\n");
}

function makeRunBundle(
  sessionId: string,
  varsSnapshot: VarsRecord,
  events: WorldEvent[],
  becauseOf: WorldEvent[],
  pinned: WorldEvent[],
): RunExportBundle {
  const history = events.slice(0, MAX_HISTORY_EXPORT).map((event) => sanitizeEvent(event));
  const turningPoints = becauseOf.slice(0, 10).map((event) => sanitizeEvent(event));
  const pinnedItems = pinned.slice(0, 80).map((event) => sanitizeEvent(event));

  return {
    export_schema_version: RUN_EXPORT_SCHEMA_VERSION,
    chronicle_schema_version: CHRONICLE_SCHEMA_VERSION,
    client_version: CLIENT_VERSION,
    session_id: sessionId,
    generated_at: new Date().toISOString(),
    history_count: history.length,
    pinned_count: pinnedItems.length,
    turning_points_count: turningPoints.length,
    vars_snapshot: sanitizeVars(varsSnapshot),
    recent_history: history,
    pinned_items: pinnedItems,
    key_turning_points: turningPoints,
  };
}

export function buildShareTeaser(
  sessionId: string,
  events: WorldEvent[],
  becauseOf: WorldEvent[],
): string {
  const turningPoint = becauseOf[0];
  const latest = events[0];
  const hook = turningPoint?.summary ?? latest?.summary ?? "A quiet thread began to unravel.";
  const followUp = latest?.summary && turningPoint?.summary !== latest.summary
    ? ` Most recently: ${latest.summary}.`
    : "";
  return `Session ${sessionId.slice(-8)}: ${hook}${followUp} The world now carries those consequences forward.`;
}

export async function copyTextToClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Fall through to textarea fallback.
    }
  };

  try {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "true");
    area.style.position = "absolute";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand("copy");
    area.remove();
    return ok;
  } catch {
    return false;
  }
}

export function exportRunArtifacts(
  sessionId: string,
  varsSnapshot: VarsRecord,
  events: WorldEvent[],
  becauseOf: WorldEvent[],
  pinned: WorldEvent[],
): RunExportBundle {
  const bundle = makeRunBundle(sessionId, varsSnapshot, events, becauseOf, pinned);

  const chronicle = buildMarkdown(
    sessionId,
    bundle.vars_snapshot,
    bundle.recent_history,
    bundle.key_turning_points,
    bundle.pinned_items,
  );
  downloadTextFile(
    "chronicle.md",
    chronicle,
    "text/markdown;charset=utf-8",
  );
  downloadTextFile(
    "run.json",
    JSON.stringify(bundle, null, 2),
    "application/json;charset=utf-8",
  );

  return bundle;
}
