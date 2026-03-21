import { useEffect, useState } from "react";

import type { GuildBoardResponse, GuildQuestRecord } from "../types";
import { GuildBoard } from "./GuildBoard";
import { GuildQuestPanel } from "./GuildQuestPanel";

type GuildShellTab = "workspace" | "quests";

type GuildShellProps = {
  displayName?: string;
  canUseMentorBoard: boolean;
  guildBoard: GuildBoardResponse | null;
  guildBoardPending: boolean;
  guildBoardError: string | null;
  refreshGuildBoard: () => void;
  assignQuest: (payload: Parameters<NonNullable<React.ComponentProps<typeof GuildBoard>["onAssignQuest"]>>[0]) => Promise<void>;
  bootstrapSteward: () => Promise<void>;
  patchMemberProfile: (payload: Parameters<NonNullable<React.ComponentProps<typeof GuildBoard>["onPatchMemberProfile"]>>[0]) => Promise<void>;
  guildQuests: GuildQuestRecord[];
  guildQuestsPending: boolean;
  guildQuestsError: string | null;
  refreshGuildQuests: () => void;
};

export function GuildShell({
  displayName,
  canUseMentorBoard,
  guildBoard,
  guildBoardPending,
  guildBoardError,
  refreshGuildBoard,
  assignQuest,
  bootstrapSteward,
  patchMemberProfile,
  guildQuests,
  guildQuestsPending,
  guildQuestsError,
  refreshGuildQuests,
}: GuildShellProps) {
  const [tab, setTab] = useState<GuildShellTab>(canUseMentorBoard ? "workspace" : "quests");

  useEffect(() => {
    if (!canUseMentorBoard && tab === "workspace") {
      setTab("quests");
    }
  }, [canUseMentorBoard, tab]);

  const counts = guildBoard?.counts;
  const me = guildBoard?.me ?? null;
  const activeQuestCount = guildQuests.filter((quest) =>
    ["assigned", "accepted", "in_progress"].includes(String(quest.status || "").trim().toLowerCase()),
  ).length;

  return (
    <div className="ww-guild-shell">
      <section className="ww-guild-shell-hero">
        <div className="ww-guild-shell-copy">
          <p className="ww-guild-shell-eyebrow">Guild Workspace</p>
          <h2 className="ww-guild-shell-title">
            {displayName ? `${displayName}, shape the training commons.` : "Shape the training commons."}
          </h2>
          <p className="ww-guild-shell-subtitle">
            This is the dedicated guild surface for quest authoring, review, and contributor growth.
            It is not just another world-side tab.
          </p>
        </div>
        <div className="ww-guild-shell-metrics">
          <div className="ww-guild-shell-chip">
            {me ? `${me.profile.rank.replace(/_/g, " ")}${me.capabilities.can_manage_roles ? " steward" : me.capabilities.can_assign_quests ? " mentor" : ""}` : "guild access"}
          </div>
          <div className="ww-guild-shell-chip">
            {counts ? `${counts.resident_members} residents` : "residents loading"}
          </div>
          <div className="ww-guild-shell-chip">
            {counts ? `${counts.human_members} humans` : "humans loading"}
          </div>
          <div className="ww-guild-shell-chip">
            {counts ? `${counts.active_quests} active board quests` : "quests loading"}
          </div>
          <div className="ww-guild-shell-chip">
            {activeQuestCount} assigned to you
          </div>
        </div>
      </section>

      <div className="ww-guild-shell-tabs">
        {canUseMentorBoard && (
          <button
            className={`ww-guild-shell-tab${tab === "workspace" ? " ww-guild-shell-tab--active" : ""}`}
            onClick={() => setTab("workspace")}
          >
            Workspace
          </button>
        )}
        <button
          className={`ww-guild-shell-tab${tab === "quests" ? " ww-guild-shell-tab--active" : ""}`}
          onClick={() => setTab("quests")}
        >
          My Quests
        </button>
      </div>

      <div className="ww-guild-shell-body">
        {tab === "workspace" && canUseMentorBoard ? (
          <GuildBoard
            board={guildBoard}
            pending={guildBoardPending}
            error={guildBoardError}
            onRefresh={refreshGuildBoard}
            onAssignQuest={assignQuest}
            onBootstrapSteward={bootstrapSteward}
            onPatchMemberProfile={patchMemberProfile}
          />
        ) : (
          <GuildQuestPanel
            displayName={displayName}
            quests={guildQuests}
            pending={guildQuestsPending}
            error={guildQuestsError}
            onRefresh={refreshGuildQuests}
          />
        )}
      </div>
    </div>
  );
}
