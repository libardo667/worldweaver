import type { VarsRecord, WorldEvent } from "../types";

export type ChronicleBundle = {
  version: "chronicle.v1";
  session_id: string;
  generated_at: string;
  events_count: number;
  pinned_count: number;
  because_of_count: number;
  events: WorldEvent[];
  pinned: WorldEvent[];
  because_of: WorldEvent[];
};

function toTimestamp(value?: string | null): number {
  if (!value) {
    return 0;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
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
  events: WorldEvent[],
  becauseOf: WorldEvent[],
  pinned: WorldEvent[],
): string {
  const lines: string[] = [];
  lines.push(`# WorldWeaver Chronicle`);
  lines.push("");
  lines.push(`- Session: \`${sessionId}\``);
  lines.push(`- Generated: ${new Date().toLocaleString()}`);
  lines.push(`- Events: ${events.length}`);
  lines.push(`- Pinned: ${pinned.length}`);
  lines.push("");
  lines.push("## Because Of...");
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

export function exportChronicleRun(
  sessionId: string,
  events: WorldEvent[],
  becauseOf: WorldEvent[],
  pinned: WorldEvent[],
) {
  const bundle: ChronicleBundle = {
    version: "chronicle.v1",
    session_id: sessionId,
    generated_at: new Date().toISOString(),
    events_count: events.length,
    pinned_count: pinned.length,
    because_of_count: becauseOf.length,
    events,
    pinned,
    because_of: becauseOf,
  };

  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  downloadTextFile(
    `worldweaver-chronicle-${stamp}.md`,
    buildMarkdown(sessionId, events, becauseOf, pinned),
    "text/markdown;charset=utf-8",
  );
  downloadTextFile(
    `worldweaver-chronicle-${stamp}.json`,
    JSON.stringify(bundle, null, 2),
    "application/json;charset=utf-8",
  );
}
