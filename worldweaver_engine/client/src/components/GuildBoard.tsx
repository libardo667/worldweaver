import { useMemo, useState } from "react";

import type { GuildBoardMember, GuildBoardResponse } from "../types";

type GuildBoardProps = {
  board: GuildBoardResponse | null;
  pending?: boolean;
  error?: string | null;
  onRefresh: () => void;
  onAssignQuest: (payload: {
    target_actor_id: string;
    title: string;
    brief: string;
    branch?: string;
    quest_band?: string;
  }) => Promise<void>;
};

function residentLabel(member: GuildBoardMember): string {
  const bits = [member.display_name];
  if (member.location) bits.push(member.location.replace(/_/g, " "));
  if (member.branches.length > 0) bits.push(member.branches.join(", "));
  return bits.join(" · ");
}

export function GuildBoard({
  board,
  pending = false,
  error,
  onRefresh,
  onAssignQuest,
}: GuildBoardProps) {
  const [targetActorId, setTargetActorId] = useState("");
  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [branch, setBranch] = useState("");
  const [questBand, setQuestBand] = useState("");

  const residents = board?.residents ?? [];
  const activeQuests = board?.active_quests ?? [];
  const me = board?.me ?? null;
  const canAssignQuests = Boolean(me?.capabilities?.can_assign_quests);

  const selectedResident = useMemo(
    () => residents.find((resident) => resident.actor_id === targetActorId) ?? null,
    [residents, targetActorId],
  );

  async function submitQuest() {
    if (!canAssignQuests || !targetActorId || !title.trim()) return;
    await onAssignQuest({
      target_actor_id: targetActorId,
      title: title.trim(),
      brief: brief.trim(),
      branch: branch.trim() || undefined,
      quest_band: questBand.trim() || undefined,
    });
    setTitle("");
    setBrief("");
    setBranch("");
    setQuestBand("");
  }

  return (
    <div className="ww-guild-board" style={{ display: "flex", flexDirection: "column", gap: "1rem", padding: "1rem" }}>
      <div className="ww-guild-board-header">
        <div>
          <h3 className="ww-info-section-title" style={{ marginBottom: "0.25rem" }}>
            Guild Board
          </h3>
          <div style={{ fontSize: "0.92rem", opacity: 0.85 }}>
            {me
              ? `${me.display_name} · ${me.profile.rank.replace(/_/g, " ")}`
              : "Signed-in guild access"}
          </div>
        </div>
        <button className="ww-recovery-strip-btn" onClick={onRefresh}>
          Refresh
        </button>
      </div>

      {error && (
        <div className="ww-recovery-strip ww-recovery-strip--error">
          <div className="ww-recovery-strip-copy">
            <p className="ww-recovery-strip-title">Guild board sync failed</p>
            <p className="ww-recovery-strip-text">{error}</p>
          </div>
        </div>
      )}

      <section className="ww-info-card" style={{ border: "1px solid var(--ww-border)", borderRadius: "8px", padding: "1rem" }}>
        <div style={{ fontWeight: 700, marginBottom: "0.4rem" }}>Mentor Tools</div>
        <div style={{ fontSize: "0.92rem", opacity: 0.85, marginBottom: "0.75rem" }}>
          {canAssignQuests
            ? "Assign structured quests to residents without entering the live world."
            : "Your current guild role can observe the board, but cannot assign quests."}
        </div>
        <div style={{ display: "grid", gap: "0.65rem" }}>
          <select
            className="ww-chat-input"
            value={targetActorId}
            onChange={(e) => setTargetActorId(e.target.value)}
            disabled={!canAssignQuests || pending}
          >
            <option value="">Choose a resident…</option>
            {residents.map((resident) => (
              <option key={resident.actor_id} value={resident.actor_id}>
                {residentLabel(resident)}
              </option>
            ))}
          </select>
          <input
            className="ww-chat-input"
            type="text"
            placeholder="Quest title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            disabled={!canAssignQuests || pending}
          />
          <textarea
            className="ww-notes-area"
            rows={4}
            placeholder="Quest brief"
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            disabled={!canAssignQuests || pending}
            style={{ minHeight: "7rem" }}
          />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.65rem" }}>
            <input
              className="ww-chat-input"
              type="text"
              placeholder="Branch"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              disabled={!canAssignQuests || pending}
            />
            <input
              className="ww-chat-input"
              type="text"
              placeholder="Quest band"
              value={questBand}
              onChange={(e) => setQuestBand(e.target.value)}
              disabled={!canAssignQuests || pending}
            />
          </div>
          {selectedResident && (
            <div style={{ fontSize: "0.88rem", opacity: 0.85 }}>
              Target: {selectedResident.display_name}
              {selectedResident.location ? ` · ${selectedResident.location.replace(/_/g, " ")}` : ""}
              {selectedResident.branches.length > 0 ? ` · ${selectedResident.branches.join(", ")}` : ""}
            </div>
          )}
          <button
            className="ww-send-btn"
            onClick={() => void submitQuest()}
            disabled={!canAssignQuests || pending || !targetActorId || !title.trim()}
            style={{ width: "fit-content", minWidth: "8rem" }}
          >
            {pending ? "Assigning..." : "Assign Quest"}
          </button>
        </div>
      </section>

      <section className="ww-info-card" style={{ border: "1px solid var(--ww-border)", borderRadius: "8px", padding: "1rem" }}>
        <div style={{ fontWeight: 700, marginBottom: "0.5rem" }}>
          Residents ({residents.length})
        </div>
        <div style={{ display: "grid", gap: "0.5rem" }}>
          {residents.slice(0, 32).map((resident) => (
            <div key={resident.actor_id} style={{ borderBottom: "1px solid var(--ww-border)", paddingBottom: "0.45rem" }}>
              <div style={{ fontWeight: 600 }}>{resident.display_name}</div>
              <div style={{ fontSize: "0.88rem", opacity: 0.8 }}>
                {resident.rank.replace(/_/g, " ")} · {resident.quest_band}
                {resident.location ? ` · ${resident.location.replace(/_/g, " ")}` : ""}
              </div>
              {resident.branches.length > 0 && (
                <div style={{ fontSize: "0.84rem", opacity: 0.75 }}>
                  {resident.branches.join(", ")}
                </div>
              )}
            </div>
          ))}
          {residents.length === 0 && (
            <div style={{ opacity: 0.8 }}>No resident members visible yet.</div>
          )}
        </div>
      </section>

      <section className="ww-info-card" style={{ border: "1px solid var(--ww-border)", borderRadius: "8px", padding: "1rem" }}>
        <div style={{ fontWeight: 700, marginBottom: "0.5rem" }}>
          Active Quests ({activeQuests.length})
        </div>
        <div style={{ display: "grid", gap: "0.65rem" }}>
          {activeQuests.slice(0, 24).map((quest) => (
            <div key={quest.quest_id} style={{ borderBottom: "1px solid var(--ww-border)", paddingBottom: "0.55rem" }}>
              <div style={{ fontWeight: 600 }}>{quest.title}</div>
              <div style={{ fontSize: "0.88rem", opacity: 0.8 }}>
                {quest.target_display_name ?? quest.target_actor_id} · {quest.status.replace(/_/g, " ")}
                {quest.branch ? ` · ${quest.branch}` : ""}
              </div>
              {quest.brief && (
                <div style={{ fontSize: "0.9rem", marginTop: "0.2rem", opacity: 0.9 }}>{quest.brief}</div>
              )}
            </div>
          ))}
          {activeQuests.length === 0 && (
            <div style={{ opacity: 0.8 }}>No active quests yet.</div>
          )}
        </div>
      </section>
    </div>
  );
}
