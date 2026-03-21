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
  onBootstrapSteward: () => Promise<void>;
  onPatchMemberProfile: (payload: {
    actor_id: string;
    rank?: string;
    branches?: string[];
    mentor_actor_ids?: string[];
    quest_band?: string;
    review_status?: Record<string, unknown>;
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
  onBootstrapSteward,
  onPatchMemberProfile,
}: GuildBoardProps) {
  const [targetActorId, setTargetActorId] = useState("");
  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [branch, setBranch] = useState("");
  const [questBand, setQuestBand] = useState("");
  const [memberActorId, setMemberActorId] = useState("");
  const [memberRank, setMemberRank] = useState("apprentice");
  const [memberQuestBand, setMemberQuestBand] = useState("");
  const [memberBranches, setMemberBranches] = useState("");
  const [memberMentors, setMemberMentors] = useState("");
  const [memberIsMentor, setMemberIsMentor] = useState(false);
  const [memberIsSteward, setMemberIsSteward] = useState(false);

  const residents = board?.residents ?? [];
  const humans = board?.humans ?? [];
  const activeQuests = board?.active_quests ?? [];
  const resolvedQuests = board?.recently_resolved_quests ?? [];
  const me = board?.me ?? null;
  const canAssignQuests = Boolean(me?.capabilities?.can_assign_quests);
  const canManageRoles = Boolean(me?.capabilities?.can_manage_roles);
  const canBootstrapSteward = Boolean(me?.capabilities?.can_bootstrap_steward) && !canManageRoles;
  const allMembers = [...humans, ...residents];
  const memberByActorId = useMemo(
    () => new Map(allMembers.map((member) => [member.actor_id, member])),
    [allMembers],
  );

  const selectedResident = useMemo(
    () => residents.find((resident) => resident.actor_id === targetActorId) ?? null,
    [residents, targetActorId],
  );
  const selectedMember = useMemo(
    () => allMembers.find((member) => member.actor_id === memberActorId) ?? null,
    [allMembers, memberActorId],
  );

  function hydrateMemberForm(actorId: string) {
    setMemberActorId(actorId);
    const next = allMembers.find((member) => member.actor_id === actorId) ?? null;
    if (!next) return;
    setMemberRank(next.rank || "apprentice");
    setMemberQuestBand(next.quest_band || "");
    setMemberBranches((next.branches ?? []).join(", "));
    setMemberMentors((next.mentor_actor_ids ?? []).join(", "));
    const reviewStatus = next.review_status ?? {};
    const governanceRoles = Array.isArray(reviewStatus.governance_roles)
      ? reviewStatus.governance_roles.map((role) => String(role || "").trim().toLowerCase())
      : [];
    const guildRole = String(reviewStatus.guild_role || "").trim().toLowerCase();
    setMemberIsSteward(governanceRoles.includes("steward") || guildRole === "steward");
    setMemberIsMentor(
      governanceRoles.includes("mentor") || guildRole === "mentor" || guildRole === "steward"
    );
  }

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

  async function submitMemberProfile() {
    if (!canManageRoles || !memberActorId) return;
    const governanceRoles = [
      ...(memberIsSteward ? ["steward"] : []),
      ...(memberIsMentor ? ["mentor"] : []),
    ];
    await onPatchMemberProfile({
      actor_id: memberActorId,
      rank: memberRank,
      quest_band: memberQuestBand.trim() || undefined,
      branches: memberBranches
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      mentor_actor_ids: memberMentors
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      review_status: {
        ...(selectedMember?.review_status ?? {}),
        governance_roles: governanceRoles,
        guild_role: memberIsSteward ? "steward" : memberIsMentor ? "mentor" : "member",
        can_assign_quests: memberIsMentor || memberIsSteward || memberRank === "elder",
        can_manage_roles: memberIsSteward,
      },
    });
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

      {canBootstrapSteward && (
        <section className="ww-info-card" style={{ border: "1px solid var(--ww-border)", borderRadius: "8px", padding: "1rem" }}>
          <div style={{ fontWeight: 700, marginBottom: "0.4rem" }}>Steward Bootstrap</div>
          <div style={{ fontSize: "0.92rem", opacity: 0.85, marginBottom: "0.75rem" }}>
            No guild steward has been labeled yet. Claiming this threshold will make your account a steward and mentor so you can govern the board.
          </div>
          <button
            className="ww-send-btn"
            onClick={() => void onBootstrapSteward()}
            disabled={pending}
            style={{ width: "fit-content", minWidth: "10rem" }}
          >
            {pending ? "Claiming..." : "Claim Steward Threshold"}
          </button>
        </section>
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
        <div style={{ fontWeight: 700, marginBottom: "0.4rem" }}>Steward Tools</div>
        <div style={{ fontSize: "0.92rem", opacity: 0.85, marginBottom: "0.75rem" }}>
          {canManageRoles
            ? "Promote humans into mentor or steward roles, and tune guild rank and branches for any member."
            : "Steward tools are locked unless this account carries steward authority."}
        </div>
        <div style={{ display: "grid", gap: "0.65rem" }}>
          <select
            className="ww-chat-input"
            value={memberActorId}
            onChange={(e) => hydrateMemberForm(e.target.value)}
            disabled={!canManageRoles || pending}
          >
            <option value="">Choose a member…</option>
            {allMembers.map((member) => (
              <option key={member.actor_id} value={member.actor_id}>
                {member.display_name} · {member.member_type} · {member.rank}
              </option>
            ))}
          </select>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.65rem" }}>
            <select
              className="ww-chat-input"
              value={memberRank}
              onChange={(e) => setMemberRank(e.target.value)}
              disabled={!canManageRoles || pending || !memberActorId}
            >
              {["apprentice", "journeyman", "guild_member", "elder"].map((rank) => (
                <option key={rank} value={rank}>
                  {rank.replace(/_/g, " ")}
                </option>
              ))}
            </select>
            <input
              className="ww-chat-input"
              type="text"
              placeholder="Quest band"
              value={memberQuestBand}
              onChange={(e) => setMemberQuestBand(e.target.value)}
              disabled={!canManageRoles || pending || !memberActorId}
            />
          </div>
          <input
            className="ww-chat-input"
            type="text"
            placeholder="Branches (comma separated)"
            value={memberBranches}
            onChange={(e) => setMemberBranches(e.target.value)}
            disabled={!canManageRoles || pending || !memberActorId}
          />
          <input
            className="ww-chat-input"
            type="text"
            placeholder="Mentor actor ids (comma separated)"
            value={memberMentors}
            onChange={(e) => setMemberMentors(e.target.value)}
            disabled={!canManageRoles || pending || !memberActorId}
          />
          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", opacity: !canManageRoles || !memberActorId ? 0.6 : 1 }}>
            <input
              type="checkbox"
              checked={memberIsMentor}
              onChange={(e) => setMemberIsMentor(e.target.checked)}
              disabled={!canManageRoles || pending || !memberActorId}
            />
            Mentor role
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", opacity: !canManageRoles || !memberActorId ? 0.6 : 1 }}>
            <input
              type="checkbox"
              checked={memberIsSteward}
              onChange={(e) => setMemberIsSteward(e.target.checked)}
              disabled={!canManageRoles || pending || !memberActorId}
            />
            Steward role
          </label>
          <button
            className="ww-send-btn"
            onClick={() => void submitMemberProfile()}
            disabled={!canManageRoles || pending || !memberActorId}
            style={{ width: "fit-content", minWidth: "8rem" }}
          >
            {pending ? "Saving..." : "Save Member"}
          </button>
        </div>
      </section>

      <section className="ww-info-card" style={{ border: "1px solid var(--ww-border)", borderRadius: "8px", padding: "1rem" }}>
        <div style={{ fontWeight: 700, marginBottom: "0.5rem" }}>
          Humans ({humans.length})
        </div>
        <div style={{ display: "grid", gap: "0.5rem", marginBottom: "1rem" }}>
          {humans.slice(0, 24).map((human) => (
            <div key={human.actor_id} style={{ borderBottom: "1px solid var(--ww-border)", paddingBottom: "0.45rem" }}>
              <div style={{ fontWeight: 600 }}>{human.display_name}</div>
              <div style={{ fontSize: "0.88rem", opacity: 0.8 }}>
                {human.rank.replace(/_/g, " ")}
                {human.location ? ` · ${human.location.replace(/_/g, " ")}` : ""}
              </div>
              {human.review_status && (
                <div style={{ fontSize: "0.84rem", opacity: 0.75 }}>
                  {Array.isArray(human.review_status.governance_roles)
                    ? (human.review_status.governance_roles as string[]).join(", ")
                    : String(human.review_status.guild_role || human.review_status.role || "").trim()}
                </div>
              )}
            </div>
          ))}
          {humans.length === 0 && (
            <div style={{ opacity: 0.8 }}>No human guild members visible yet.</div>
          )}
        </div>

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
          {activeQuests.slice(0, 24).map((quest) => {
            const targetMember = memberByActorId.get(quest.target_actor_id) ?? null;
            const activityLog = Array.isArray(quest.activity_log) ? quest.activity_log : [];
            return (
              <div key={quest.quest_id} style={{ borderBottom: "1px solid var(--ww-border)", paddingBottom: "0.55rem" }}>
                <div style={{ fontWeight: 600 }}>{quest.title}</div>
                <div style={{ fontSize: "0.88rem", opacity: 0.8 }}>
                  {quest.target_display_name ?? quest.target_actor_id} · {quest.status.replace(/_/g, " ")}
                  {quest.branch ? ` · ${quest.branch}` : ""}
                  {quest.quest_band ? ` · ${quest.quest_band}` : ""}
                </div>
                {targetMember && (
                  <div style={{ fontSize: "0.84rem", opacity: 0.75, marginTop: "0.15rem" }}>
                    {targetMember.rank.replace(/_/g, " ")}
                    {targetMember.location ? ` · ${targetMember.location.replace(/_/g, " ")}` : ""}
                    {targetMember.last_updated_at
                      ? ` · seen ${new Date(targetMember.last_updated_at).toLocaleString()}`
                      : ""}
                  </div>
                )}
                {quest.brief && (
                  <div style={{ fontSize: "0.9rem", marginTop: "0.2rem", opacity: 0.9 }}>{quest.brief}</div>
                )}
                {quest.progress_note && (
                  <div style={{ fontSize: "0.9rem", marginTop: "0.35rem" }}>
                    <strong>Progress:</strong> {quest.progress_note}
                  </div>
                )}
                {quest.outcome_summary && (
                  <div style={{ fontSize: "0.9rem", marginTop: "0.25rem" }}>
                    <strong>Outcome:</strong> {quest.outcome_summary}
                  </div>
                )}
                {activityLog.length > 0 && (
                  <div style={{ fontSize: "0.84rem", marginTop: "0.35rem", display: "grid", gap: "0.18rem" }}>
                    <strong>Timeline</strong>
                    {activityLog.slice(-4).reverse().map((entry, idx) => {
                      const summary = String(entry["summary"] || "").trim();
                      const ts = String(entry["ts"] || "").trim();
                      const kind = String(entry["kind"] || "").trim();
                      return (
                        <div key={`${quest.quest_id}-activity-${idx}`} style={{ opacity: 0.82 }}>
                          {ts ? `${new Date(ts).toLocaleString()} · ` : ""}
                          {kind ? `${kind.replace(/_/g, " ")} · ` : ""}
                          {summary || "quest activity recorded"}
                        </div>
                      );
                    })}
                  </div>
                )}
                <div style={{ fontSize: "0.82rem", opacity: 0.7, marginTop: "0.25rem" }}>
                  Assigned {quest.created_at ? new Date(quest.created_at).toLocaleString() : "recently"}
                  {quest.updated_at ? ` · updated ${new Date(quest.updated_at).toLocaleString()}` : ""}
                  {quest.accepted_at ? ` · accepted ${new Date(quest.accepted_at).toLocaleString()}` : ""}
                </div>
              </div>
            );
          })}
          {activeQuests.length === 0 && (
            <div style={{ opacity: 0.8 }}>No active quests yet.</div>
          )}
        </div>
      </section>

      <section className="ww-info-card" style={{ border: "1px solid var(--ww-border)", borderRadius: "8px", padding: "1rem" }}>
        <div style={{ fontWeight: 700, marginBottom: "0.5rem" }}>
          Recently Resolved ({resolvedQuests.length})
        </div>
        <div style={{ display: "grid", gap: "0.65rem" }}>
          {resolvedQuests.slice(0, 12).map((quest) => {
            const activityLog = Array.isArray(quest.activity_log) ? quest.activity_log : [];
            return (
              <div key={`resolved-${quest.quest_id}`} style={{ borderBottom: "1px solid var(--ww-border)", paddingBottom: "0.55rem" }}>
                <div style={{ fontWeight: 600 }}>{quest.title}</div>
                <div style={{ fontSize: "0.88rem", opacity: 0.8 }}>
                  {quest.target_display_name ?? quest.target_actor_id} · {quest.status.replace(/_/g, " ")}
                  {quest.branch ? ` · ${quest.branch}` : ""}
                </div>
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
                        <div key={`resolved-${quest.quest_id}-activity-${idx}`} style={{ opacity: 0.82 }}>
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
          {resolvedQuests.length === 0 && (
            <div style={{ opacity: 0.8 }}>No recently resolved quests yet.</div>
          )}
        </div>
      </section>
    </div>
  );
}
