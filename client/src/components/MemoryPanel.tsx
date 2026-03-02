import { useMemo, useState } from "react";
import { FactsSearch } from "./FactsSearch";
import {
  loadPinnedFacts,
  savePinnedFacts,
  togglePinnedFact,
} from "../state/pinsStore";
import type { WorldEvent } from "../types";

type MemoryPanelProps = {
  events: WorldEvent[];
  facts: WorldEvent[];
  searchPending: boolean;
  onSearch: (query: string) => Promise<void>;
};

function timestampLabel(value?: string | null): string {
  if (!value) {
    return "unknown";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "unknown";
  }
  return parsed.toLocaleTimeString();
}

export function MemoryPanel({
  events,
  facts,
  searchPending,
  onSearch,
}: MemoryPanelProps) {
  const [pins, setPins] = useState<WorldEvent[]>(() => loadPinnedFacts());
  const pinnedIds = useMemo(() => new Set(pins.map((fact) => fact.id)), [pins]);

  function handleTogglePin(fact: WorldEvent) {
    setPins((prev) => {
      const next = togglePinnedFact(prev, fact).pins;
      savePinnedFacts(next);
      return next;
    });
  }

  return (
    <aside className="panel memory-panel">
      <header className="panel-header">
        <h2>Memory</h2>
      </header>

      <section>
        <h4>Recent History</h4>
        <ul className="memory-list">
          {events.slice(0, 8).map((event) => (
            <li key={event.id}>
              <small>{timestampLabel(event.created_at)}</small>
              <p>{event.summary}</p>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h4>Pinned Facts</h4>
        {pins.length === 0 ? (
          <p className="muted">Pin facts from search results to keep them in view.</p>
        ) : (
          <ul className="fact-card-list pinned-facts-list">
            {pins.map((fact) => (
              <li key={`pin-${fact.id}`}>
                <article className="fact-card is-pinned">
                  <header>
                    <small>{fact.event_type}</small>
                    <button
                      type="button"
                      className="text-btn fact-pin-btn is-pinned"
                      onClick={() => handleTogglePin(fact)}
                    >
                      Unpin
                    </button>
                  </header>
                  <p>{fact.summary}</p>
                </article>
              </li>
            ))}
          </ul>
        )}
      </section>

      <FactsSearch
        facts={facts}
        searchPending={searchPending}
        onSearch={onSearch}
        pinnedIds={pinnedIds}
        onTogglePin={handleTogglePin}
      />
    </aside>
  );
}
