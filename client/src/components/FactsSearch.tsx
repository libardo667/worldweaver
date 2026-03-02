import { FormEvent, useState } from "react";
import type { WorldEvent } from "../types";

type FactsSearchProps = {
  facts: WorldEvent[];
  searchPending: boolean;
  onSearch: (query: string) => Promise<void>;
  pinnedIds: Set<number>;
  onTogglePin: (fact: WorldEvent) => void;
};

export function FactsSearch({
  facts,
  searchPending,
  onSearch,
  pinnedIds,
  onTogglePin,
}: FactsSearchProps) {
  const [query, setQuery] = useState("");
  const [hasSearched, setHasSearched] = useState(false);

  async function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      return;
    }
    setHasSearched(true);
    await onSearch(trimmed);
  }

  return (
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

      {!searchPending && hasSearched && facts.length === 0 ? (
        <p className="muted">No matching facts found yet.</p>
      ) : null}

      <ul className="fact-card-list">
        {facts.slice(0, 8).map((fact) => {
          const isPinned = pinnedIds.has(fact.id);
          return (
            <li key={`fact-${fact.id}`}>
              <article className="fact-card">
                <header>
                  <small>{fact.event_type}</small>
                  <button
                    type="button"
                    className={`text-btn fact-pin-btn ${isPinned ? "is-pinned" : ""}`}
                    onClick={() => onTogglePin(fact)}
                  >
                    {isPinned ? "Unpin" : "Pin"}
                  </button>
                </header>
                <p>{fact.summary}</p>
              </article>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
