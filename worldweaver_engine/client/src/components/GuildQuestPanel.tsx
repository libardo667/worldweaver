import type { GuildQuestRecord } from "../types";

type GuildQuestPanelProps = {
  displayName?: string;
  quests: GuildQuestRecord[];
  pending?: boolean;
  error?: string | null;
  onRefresh: () => void;
};

function objectiveSummary(quest: GuildQuestRecord): string {
  const objectiveType = String(quest.objective_type || "").trim();
  const location = String(quest.target_location || "").trim();
  const person = String(quest.target_person || "").trim();
  const item = String(quest.target_item || "").trim();
  if (objectiveType === "visit_location") return location ? `Go to ${location}` : "";
  if (objectiveType === "observe_location") return location ? `Observe conditions at ${location}` : "";
  if (objectiveType === "speak_with_person") return person ? `Speak with ${person}` : "";
  if (objectiveType === "meet_person") {
    if (person && location) return `Meet ${person} at ${location}`;
    if (person) return `Meet ${person}`;
  }
  if (objectiveType === "deliver_message") return person ? `Deliver a message to ${person}` : "Deliver the message";
  if (objectiveType === "find_item") {
    if (item && location) return `Find ${item} at ${location}`;
    if (item) return `Find ${item}`;
  }
  if (Array.isArray(quest.success_signals) && quest.success_signals.length > 0) {
    return quest.success_signals[0] ?? "";
  }
  return "";
}

export function GuildQuestPanel({
  displayName,
  quests,
  pending = false,
  error,
  onRefresh,
}: GuildQuestPanelProps) {
  const active = quests.filter((quest) => ["assigned", "accepted", "in_progress"].includes(quest.status));
  const resolved = quests.filter((quest) => ["completed", "reviewed", "declined", "cancelled"].includes(quest.status));

  return (
    <div className="ww-guild-board" style={{ display: "flex", flexDirection: "column", gap: "1rem", padding: "1rem" }}>
      <div className="ww-guild-board-header">
        <div>
          <h3 className="ww-info-section-title" style={{ marginBottom: "0.25rem" }}>
            My Guild Quests
          </h3>
          <div style={{ fontSize: "0.92rem", opacity: 0.85 }}>
            {displayName ? `${displayName} · assigned work and quest trail` : "Assigned work and quest trail"}
          </div>
        </div>
        <button className="ww-recovery-strip-btn" onClick={onRefresh}>
          Refresh
        </button>
      </div>

      {error && (
        <div className="ww-recovery-strip ww-recovery-strip--error">
          <div className="ww-recovery-strip-copy">
            <p className="ww-recovery-strip-title">Quest sync failed</p>
            <p className="ww-recovery-strip-text">{error}</p>
          </div>
        </div>
      )}

      <section className="ww-info-card" style={{ border: "1px solid var(--ww-border)", borderRadius: "8px", padding: "1rem" }}>
        <div style={{ fontWeight: 700, marginBottom: "0.5rem" }}>
          Active Quests ({active.length})
        </div>
        <div style={{ display: "grid", gap: "0.75rem" }}>
          {active.map((quest) => {
            const activityLog = Array.isArray(quest.activity_log) ? quest.activity_log : [];
            const objective = objectiveSummary(quest);
            return (
              <div key={`active-quest-${quest.quest_id}`} style={{ borderBottom: "1px solid var(--ww-border)", paddingBottom: "0.65rem" }}>
                <div style={{ fontWeight: 600 }}>{quest.title}</div>
                <div style={{ fontSize: "0.88rem", opacity: 0.8 }}>
                  {quest.status.replace(/_/g, " ")}
                  {quest.branch ? ` · ${quest.branch}` : ""}
                  {quest.quest_band ? ` · ${quest.quest_band}` : ""}
                </div>
                {quest.brief && (
                  <div style={{ fontSize: "0.92rem", marginTop: "0.25rem", opacity: 0.9 }}>
                    {quest.brief}
                  </div>
                )}
                {objective && (
                  <div style={{ fontSize: "0.9rem", marginTop: "0.3rem" }}>
                    <strong>Objective:</strong> {objective}
                  </div>
                )}
                {Array.isArray(quest.success_signals) && quest.success_signals.length > 0 && (
                  <div style={{ fontSize: "0.84rem", marginTop: "0.2rem", opacity: 0.78 }}>
                    Signals: {quest.success_signals.join(" · ")}
                  </div>
                )}
                {quest.progress_note && (
                  <div style={{ fontSize: "0.9rem", marginTop: "0.35rem" }}>
                    <strong>Progress:</strong> {quest.progress_note}
                  </div>
                )}
                {activityLog.length > 0 && (
                  <div style={{ fontSize: "0.84rem", marginTop: "0.45rem", display: "grid", gap: "0.18rem" }}>
                    <strong>Recent activity</strong>
                    {activityLog.slice(-5).reverse().map((entry, idx) => {
                      const summary = String(entry["summary"] || "").trim();
                      const ts = String(entry["ts"] || "").trim();
                      const kind = String(entry["kind"] || "").trim();
                      return (
                        <div key={`active-quest-${quest.quest_id}-activity-${idx}`} style={{ opacity: 0.82 }}>
                          {ts ? `${new Date(ts).toLocaleString()} · ` : ""}
                          {kind ? `${kind.replace(/_/g, " ")} · ` : ""}
                          {summary || "quest activity recorded"}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
          {active.length === 0 && (
            <div style={{ opacity: 0.8 }}>
              {pending ? "Checking for assigned quests..." : "No active quests are assigned to this account right now."}
            </div>
          )}
        </div>
      </section>

      <section className="ww-info-card" style={{ border: "1px solid var(--ww-border)", borderRadius: "8px", padding: "1rem" }}>
        <div style={{ fontWeight: 700, marginBottom: "0.5rem" }}>
          Resolved Quests ({resolved.length})
        </div>
        <div style={{ display: "grid", gap: "0.75rem" }}>
          {resolved.slice(0, 12).map((quest) => {
            const activityLog = Array.isArray(quest.activity_log) ? quest.activity_log : [];
            const objective = objectiveSummary(quest);
            return (
              <div key={`resolved-quest-${quest.quest_id}`} style={{ borderBottom: "1px solid var(--ww-border)", paddingBottom: "0.65rem" }}>
                <div style={{ fontWeight: 600 }}>{quest.title}</div>
                <div style={{ fontSize: "0.88rem", opacity: 0.8 }}>
                  {quest.status.replace(/_/g, " ")}
                  {quest.branch ? ` · ${quest.branch}` : ""}
                </div>
                {objective && (
                  <div style={{ fontSize: "0.9rem", marginTop: "0.3rem" }}>
                    <strong>Objective:</strong> {objective}
                  </div>
                )}
                {quest.outcome_summary && (
                  <div style={{ fontSize: "0.9rem", marginTop: "0.25rem" }}>
                    <strong>Outcome:</strong> {quest.outcome_summary}
                  </div>
                )}
                {activityLog.length > 0 && (
                  <div style={{ fontSize: "0.84rem", marginTop: "0.35rem", display: "grid", gap: "0.18rem" }}>
                    {activityLog.slice(-3).reverse().map((entry, idx) => {
                      const summary = String(entry["summary"] || "").trim();
                      const ts = String(entry["ts"] || "").trim();
                      return (
                        <div key={`resolved-quest-${quest.quest_id}-activity-${idx}`} style={{ opacity: 0.82 }}>
                          {ts ? `${new Date(ts).toLocaleString()} · ` : ""}
                          {summary || "quest activity recorded"}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
          {resolved.length === 0 && (
            <div style={{ opacity: 0.8 }}>
              No resolved quests yet.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
