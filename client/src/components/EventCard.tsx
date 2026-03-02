import type { WorldEvent } from "../types";

type EventCardProps = {
  event: WorldEvent;
  pinned: boolean;
  onTogglePin?: (event: WorldEvent) => void;
};

function formatTimestamp(value?: string | null): string {
  if (!value) {
    return "unknown time";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "unknown time";
  }
  return parsed.toLocaleString();
}

function hasDelta(event: WorldEvent): boolean {
  return Object.keys(event.world_state_delta ?? {}).length > 0;
}

export function EventCard({ event, pinned, onTogglePin }: EventCardProps) {
  const impact = event.event_type === "permanent_change" || hasDelta(event) ? "permanent_change" : "normal";

  return (
    <article className={`event-card ${impact === "permanent_change" ? "impact-strong" : ""}`}>
      <header className="event-card-head">
        <div>
          <small>{formatTimestamp(event.created_at)}</small>
          <p className="event-type">{event.event_type}</p>
        </div>
        <div className="event-card-actions">
          <span className={`impact-badge ${impact === "permanent_change" ? "strong" : ""}`}>
            {impact === "permanent_change" ? "Permanent change" : "Normal"}
          </span>
          {onTogglePin ? (
            <button
              type="button"
              className={`text-btn ${pinned ? "fact-pin-btn is-pinned" : ""}`}
              aria-label={pinned ? `Unpin event ${event.id}` : `Pin event ${event.id}`}
              onClick={() => onTogglePin(event)}
            >
              {pinned ? "Unpin" : "Pin"}
            </button>
          ) : null}
        </div>
      </header>
      <p>{event.summary}</p>
    </article>
  );
}
