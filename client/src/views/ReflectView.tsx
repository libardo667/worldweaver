import { useMemo, useState } from "react";

import { BecauseOfPanel } from "../components/BecauseOfPanel";
import { EventCard } from "../components/EventCard";
import { ExportPanel } from "../components/ExportPanel";
import { Timeline } from "../components/Timeline";
import {
  loadPinnedFacts,
  savePinnedFacts,
  togglePinnedFact,
} from "../state/pinsStore";
import type { VarsRecord, WorldEvent } from "../types";
import { selectBecauseOfEvents } from "../utils/exportRun";

export type ReflectViewProps = {
  sessionId: string;
  varsSnapshot: VarsRecord;
  events: WorldEvent[];
  pending: boolean;
  historyLimit: number;
  onRefreshHistory: (limit: number) => Promise<void>;
};

export function ReflectView({
  sessionId,
  varsSnapshot,
  events,
  pending,
  historyLimit,
  onRefreshHistory,
}: ReflectViewProps) {
  const [pins, setPins] = useState<WorldEvent[]>(() => loadPinnedFacts());
  const [limitChoice, setLimitChoice] = useState(String(historyLimit));

  const pinnedIds = useMemo(() => new Set(pins.map((event) => event.id)), [pins]);
  const becauseOfEvents = useMemo(() => selectBecauseOfEvents(events, 5), [events]);
  const pinnedForSession = useMemo(
    () => pins.filter((event) => !event.session_id || event.session_id === sessionId),
    [pins, sessionId],
  );

  async function applyHistoryLimit() {
    const parsed = Number(limitChoice);
    if (!Number.isFinite(parsed) || parsed < 10) {
      return;
    }
    await onRefreshHistory(parsed);
  }

  function handleTogglePin(event: WorldEvent) {
    setPins((previous) => {
      const next = togglePinnedFact(previous, event).pins;
      savePinnedFacts(next);
      return next;
    });
  }

  return (
    <main className="reflect-view" aria-label="Reflect mode">
      <section className="panel reflect-panel reflect-controls">
        <header className="panel-header">
          <h2>Reflect Mode</h2>
          <span className="panel-meta">Legends-style chronicle</span>
        </header>
        <div className="reflect-controls-row">
          <label htmlFor="reflect-limit">Timeline limit</label>
          <select
            id="reflect-limit"
            value={limitChoice}
            onChange={(event) => setLimitChoice(event.target.value)}
          >
            <option value="25">25</option>
            <option value="50">50</option>
            <option value="75">75</option>
            <option value="100">100</option>
          </select>
          <button type="button" className="text-btn" onClick={applyHistoryLimit}>
            Refresh
          </button>
        </div>
        <ExportPanel
          sessionId={sessionId}
          varsSnapshot={varsSnapshot}
          events={events}
          becauseOfEvents={becauseOfEvents}
          pinnedEvents={pinnedForSession}
        />
      </section>

      <section className="panel reflect-panel pinned-panel">
        <header className="panel-header">
          <h3>Pinned</h3>
          <span className="panel-meta">{pinnedForSession.length} pinned events</span>
        </header>
        {pinnedForSession.length === 0 ? (
          <p className="muted">Pin timeline events to keep key world shifts visible.</p>
        ) : (
          <ul className="timeline-list">
            {pinnedForSession.map((event) => (
              <li key={`pinned-${event.id}`}>
                <EventCard
                  event={event}
                  pinned={true}
                  onTogglePin={handleTogglePin}
                />
              </li>
            ))}
          </ul>
        )}
      </section>

      <BecauseOfPanel
        events={becauseOfEvents}
        onTogglePin={handleTogglePin}
        pinnedIds={pinnedIds}
      />

      <Timeline
        events={events}
        pinnedIds={pinnedIds}
        pending={pending}
        onTogglePin={handleTogglePin}
      />
    </main>
  );
}
