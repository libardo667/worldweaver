import type { WorldEvent } from "../types";
import { EventCard } from "./EventCard";

type BecauseOfPanelProps = {
  events: WorldEvent[];
  onTogglePin: (event: WorldEvent) => void;
  pinnedIds: Set<number>;
};

export function BecauseOfPanel({
  events,
  onTogglePin,
  pinnedIds,
}: BecauseOfPanelProps) {
  return (
    <section className="panel reflect-panel because-panel">
      <header className="panel-header">
        <h3>Because Of...</h3>
        <span className="panel-meta">{events.length} high-salience events</span>
      </header>
      {events.length === 0 ? (
        <p className="muted">Need more recorded history to infer causal links.</p>
      ) : (
        <ul className="timeline-list">
          {events.map((event) => (
            <li key={`because-${event.id}`}>
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
