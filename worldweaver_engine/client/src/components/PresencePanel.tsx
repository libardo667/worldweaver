import type { RestMetricsResponse, RestMetricsSession } from "../api/wwClient";

type PresencePanelProps = {
  metrics: RestMetricsResponse | null;
  sessionId: string;
  onRefresh: () => void;
};

function presenceStatusLabel(status: string): string {
  switch (status) {
    case "resting":
      return "Resting";
    case "returning":
      return "Returning";
    default:
      return "Active";
  }
}

function entityLabel(entityType: string): string {
  return entityType === "agent" ? "AI" : "Human";
}

function formatRemainingMinutes(minutes: number | null): string | null {
  if (minutes == null) return null;
  if (minutes >= 120) {
    return `${Math.round((minutes / 60) * 10) / 10}h left`;
  }
  if (minutes >= 1) {
    return `${Math.round(minutes)}m left`;
  }
  return "waking now";
}

function formatTimestamp(raw: string | null): string | null {
  if (!raw) return null;
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function PresenceSection({
  title,
  sessions,
  sessionId,
}: {
  title: string;
  sessions: RestMetricsSession[];
  sessionId: string;
}) {
  if (sessions.length === 0) {
    return (
      <section className="ww-presence-section">
        <div className="ww-presence-section-head">
          <h4 className="ww-info-section-title">{title}</h4>
        </div>
        <p className="ww-digest-empty">No one in this state right now.</p>
      </section>
    );
  }

  return (
    <section className="ww-presence-section">
      <div className="ww-presence-section-head">
        <h4 className="ww-info-section-title">
          {title} <span className="ww-presence-count">({sessions.length})</span>
        </h4>
      </div>
      <ul className="ww-presence-list">
        {sessions.map((entry) => {
          const remaining = formatRemainingMinutes(entry.remaining_minutes);
          const untilLabel = formatTimestamp(entry.rest_until);
          return (
            <li
              key={entry.session_id}
              className={`ww-presence-entry${entry.session_id === sessionId ? " ww-presence-entry--you" : ""}`}
            >
              <div className="ww-presence-line">
                <span className="ww-roster-name">
                  {entry.display_name}
                  {entry.session_id === sessionId && <span className="ww-roster-you"> (you)</span>}
                </span>
                <div className="ww-presence-chips">
                  <span className={`ww-presence-pill ww-presence-pill--${entry.entity_type}`}>
                    {entityLabel(entry.entity_type)}
                  </span>
                  <span className={`ww-presence-pill ww-presence-pill--${entry.status}`}>
                    {presenceStatusLabel(entry.status)}
                  </span>
                  {entry.pending_hits > 0 && (
                    <span className="ww-presence-pill ww-presence-pill--pending">
                      Settling {entry.pending_hits}
                    </span>
                  )}
                </div>
              </div>
              <div className="ww-presence-meta">
                <span>{entry.location.replace(/_/g, " ")}</span>
                {remaining && <span>{remaining}</span>}
                {untilLabel && <span>until {untilLabel}</span>}
              </div>
              {(entry.rest_reason || entry.pending_reason) && (
                <div className="ww-presence-note">
                  {entry.rest_reason || entry.pending_reason}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function PresencePanel({ metrics, sessionId, onRefresh }: PresencePanelProps) {
  if (!metrics) {
    return (
      <div className="ww-presence-tab">
        <div className="ww-presence-empty">
          <p className="ww-digest-empty">Loading shard presence…</p>
          <button className="ww-presence-refresh" onClick={onRefresh}>
            Refresh
          </button>
        </div>
      </div>
    );
  }

  const active = metrics.sessions.filter((entry) => entry.status === "active");
  const resting = metrics.sessions.filter((entry) => entry.status === "resting");
  const returning = metrics.sessions.filter((entry) => entry.status === "returning");
  const humans = metrics.sessions.filter((entry) => entry.entity_type === "human").length;
  const agents = metrics.sessions.filter((entry) => entry.entity_type === "agent").length;
  const cityLabel = (metrics.shard.city_id || metrics.shard.shard_id).replace(/_/g, " ");

  return (
    <div className="ww-presence-tab">
      <section className="ww-presence-summary">
        <div className="ww-presence-summary-copy">
          <p className="ww-presence-eyebrow">Shard Presence</p>
          <h3 className="ww-presence-title">{cityLabel}</h3>
          <p className="ww-presence-subtitle">
            {metrics.counts.total} present • {humans} human{humans === 1 ? "" : "s"} • {agents} AI
          </p>
          <p className="ww-presence-subtitle">
            default rest {metrics.rest_config.defaults.break_minutes}m break • {metrics.rest_config.defaults.sleep_hours}h sleep
            {metrics.rest_config.override_count > 0 ? ` • ${metrics.rest_config.override_count} override${metrics.rest_config.override_count === 1 ? "" : "s"}` : ""}
          </p>
        </div>
        <button className="ww-presence-refresh" onClick={onRefresh}>
          Refresh
        </button>
      </section>

      <div className="ww-presence-chip-row">
        <span className="ww-presence-chip">Active {metrics.counts.active}</span>
        <span className="ww-presence-chip">Resting {metrics.counts.resting}</span>
        <span className="ww-presence-chip">Returning {metrics.counts.returning}</span>
        <span className="ww-presence-chip">Queued {metrics.counts.pending_confirmation}</span>
      </div>

      <PresenceSection title="Active" sessions={active} sessionId={sessionId} />
      <PresenceSection title="Resting" sessions={resting} sessionId={sessionId} />
      <PresenceSection title="Returning" sessions={returning} sessionId={sessionId} />
    </div>
  );
}
