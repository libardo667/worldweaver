import type { WorldEvent } from "../types";
import { EventCard } from "./EventCard";

type TimelineProps = {
  events: WorldEvent[];
  pinnedIds: Set<number>;
  pending?: boolean;
  onTogglePin: (event: WorldEvent) => void;
};

export function Timeline({
  events,
  pinnedIds,
  pending = false,
  onTogglePin,
}: TimelineProps) {
  return (
    <section className="panel reflect-panel timeline-panel">
      <header className="panel-header">
        <h3>Timeline</h3>
        <span className="panel-meta">{pending ? "Refreshing..." : `${events.length} events`}</span>
      </header>
      {events.length === 0 && !pending ? (
        <p className="muted">No world history events yet.</p>
      ) : (
        <ul className="timeline-list">
          {events.map((event) => (
            <li key={`timeline-${event.id}`}>
              <EventCard
                event={event}
                pinned={pinnedIds.has(event.id)}
                onTogglePin={onTogglePin}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
