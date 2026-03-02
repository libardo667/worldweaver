import { FormEvent, useState } from "react";
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
  const [query, setQuery] = useState("");

  async function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      return;
    }
    await onSearch(trimmed);
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
        <h4>World Fact Search</h4>
        <form className="memory-search" onSubmit={submitSearch}>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="bridge, rumor, merchant..."
          />
          <button type="submit" disabled={searchPending || !query.trim()}>
            {searchPending ? "Searching..." : "Search"}
          </button>
        </form>
        <ul className="memory-list fact-list">
          {facts.slice(0, 6).map((fact) => (
            <li key={`fact-${fact.id}`}>
              <small>{fact.event_type}</small>
              <p>{fact.summary}</p>
            </li>
          ))}
        </ul>
      </section>
    </aside>
  );
}
