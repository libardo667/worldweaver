import type {
  PrefetchStatusResponse,
  SpatialDirectionMap,
  SpatialLead,
  VarsRecord,
} from "../types";
import { Compass } from "./Compass";

type PlacePanelProps = {
  vars: VarsRecord;
  availableDirections: SpatialDirectionMap;
  leads: SpatialLead[];
  pendingMove: boolean;
  onMove: (direction: string) => void;
  showCompass?: boolean;
  prefetchStatus?: PrefetchStatusResponse | null;
  showPrefetchStatus?: boolean;
};

function toText(value: unknown, fallback = "unknown"): string {
  const text = String(value ?? "").trim();
  return text || fallback;
}

export function PlacePanel({
  vars,
  availableDirections,
  leads,
  pendingMove,
  onMove,
  showCompass = true,
  prefetchStatus = null,
  showPrefetchStatus = false,
}: PlacePanelProps) {
  const location = toText(vars.location, "start");
  const timeOfDay = toText(vars.time_of_day, "morning");
  const weather = toText(vars.weather, "clear");
  const danger = toText(vars.danger_level, "0");

  return (
    <aside className="panel place-panel">
      <header className="panel-header">
        <h2>Place</h2>
        {showPrefetchStatus ? (
          <span className="panel-meta">
            Frontier cached: {prefetchStatus?.stubs_cached ?? 0} stubs
          </span>
        ) : null}
      </header>
      {showPrefetchStatus ? (
        <p className="panel-meta">
          TTL remaining: {prefetchStatus?.expires_in_seconds ?? 0}s
        </p>
      ) : null}
      <div className="location-card">
        <h3>{location}</h3>
        <div className="badge-row">
          <span className="badge">{timeOfDay}</span>
          <span className="badge">{weather}</span>
          <span className="badge">Danger {danger}</span>
        </div>
      </div>

      {showCompass ? (
        <>
          <Compass
            availableDirections={availableDirections}
            pending={pendingMove}
            onMove={onMove}
          />
          <p className="panel-meta">
            Bright routes are traversable now; dim routes are blocked.
          </p>
        </>
      ) : (
        <p className="panel-meta">
          Assistive compass is disabled; narrative play remains fully available.
        </p>
      )}

      <section className="lead-list">
        <h4>Directional Leads</h4>
        {leads.length === 0 ? (
          <p className="muted">No strong leads yet.</p>
        ) : (
          <ul>
            {leads.slice(0, 4).map((lead) => (
              <li key={`${lead.direction}-${lead.title}`}>
                <span>{lead.direction}</span>
                <strong>{lead.title}</strong>
              </li>
            ))}
          </ul>
        )}
      </section>
    </aside>
  );
}
