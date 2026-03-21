import { useMemo, useState } from "react";

import type { GuildBoardMember, GuildBoardResponse } from "../types";

type QuestPatternOption = {
  objectiveType: string;
  label: string;
  description: string;
};

type RubricStrength = "strong" | "developing" | "weak";

type QuestRubricItem = {
  label: string;
  strength: RubricStrength;
  summary: string;
  prompt: string;
};

type ObjectiveGuidance = {
  summary: string;
  required: string[];
  example: string;
  evidenceLabel: string;
  evidenceHelp: string;
  evidenceExamples: string[];
};

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
    objective_type?: string;
    target_location?: string;
    target_person?: string;
    target_item?: string;
    success_signals?: string[];
  }) => Promise<void>;
  onIssueStarterPack: (payload?: { target_actor_id?: string }) => Promise<void>;
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
  bits.push(member.member_type);
  if (member.location) bits.push(member.location.replace(/_/g, " "));
  if (member.branches.length > 0) bits.push(member.branches.join(", "));
  return bits.join(" · ");
}

function starterPackMeta(member: GuildBoardMember | null | undefined): Record<string, unknown> | null {
  const raw = member?.review_status?.starter_pack;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  return raw as Record<string, unknown>;
}

function questObjectiveSummary(quest: {
  objective_type?: string | null;
  target_location?: string | null;
  target_person?: string | null;
  target_item?: string | null;
  success_signals?: string[];
}): string {
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
  const signals = Array.isArray(quest.success_signals) ? quest.success_signals.filter(Boolean) : [];
  return signals[0] ?? "";
}

function objectiveGuidance(params: {
  objectiveType: string;
  targetPerson?: string;
  targetLocation?: string;
  targetItem?: string;
  selectedResident?: GuildBoardMember | null;
}): ObjectiveGuidance {
  const objectiveType = String(params.objectiveType || "").trim();
  const targetPerson = String(params.targetPerson || "").trim();
  const targetLocation = String(params.targetLocation || "").trim();
  const targetItem = String(params.targetItem || "").trim();
  const residentName = String(params.selectedResident?.display_name || "the resident").trim();

  switch (objectiveType) {
    case "visit_location":
      return {
        summary: "Use this when the resident simply needs to get somewhere real in the world.",
        required: ["Target location"],
        example: `Example task: send ${residentName} to ${targetLocation || "North Beach"} for a concrete reason.`,
        evidenceLabel: "What proof should come back?",
        evidenceHelp: "Write plain-language signs of completion. Comma-separated is fine. Do not use snake_case.",
        evidenceExamples: [
          `${residentName} arrives at ${targetLocation || "North Beach"}`,
          `${residentName} reports one concrete detail from the location`,
          `${residentName} says why the visit mattered`,
        ],
      };
    case "observe_location":
      return {
        summary: "Use this for scouting, checking conditions, or noticing details at a real place.",
        required: ["Target location"],
        example: `Example task: have ${residentName} observe conditions at ${targetLocation || "Russell"}.`,
        evidenceLabel: "What proof should come back?",
        evidenceHelp: "Write the observations you expect back in plain language. Comma-separated is fine. Do not use snake_case.",
        evidenceExamples: [
          `${residentName} describes what ${targetLocation || "the place"} looks like`,
          `${residentName} names who is there or what changed`,
          `${residentName} reports one surprising detail`,
        ],
      };
    case "speak_with_person":
      return {
        summary: "Use this when the resident should initiate a conversation or correspondence with one known member.",
        required: ["Target person"],
        example: `Example task: ask ${residentName} to reach out to ${targetPerson || "Vera Chen"} directly or in a shared local chat.`,
        evidenceLabel: "What proof would convince you the contact actually happened?",
        evidenceHelp: "Write plain-language evidence. Comma-separated is fine. Do not use snake_case or backend field names.",
        evidenceExamples: [
          `${targetPerson || "They"} replies to ${residentName}`,
          `${residentName} mentions what ${targetPerson || "they"} said`,
          `${residentName} and ${targetPerson || "the target"} exchange messages in local chat`,
        ],
      };
    case "meet_person":
      return {
        summary: "Use this when the resident should go to a real place and meet someone there.",
        required: ["Target location", "Target person"],
        example: `Example task: send ${residentName} to meet ${targetPerson || "Vera Chen"} at ${targetLocation || "North Beach"}.`,
        evidenceLabel: "What proof should come back?",
        evidenceHelp: "Write plain-language evidence for the meeting. Comma-separated is fine. Do not use snake_case.",
        evidenceExamples: [
          `${residentName} meets ${targetPerson || "the target"} at ${targetLocation || "the location"}`,
          `${residentName} reports what they discussed`,
          `${residentName} confirms one concrete detail from the meeting`,
        ],
      };
    case "find_item":
      return {
        summary: "Use this for a concrete search task. Add a real location if you know where the search should happen.",
        required: ["Target item"],
        example: `Example task: have ${residentName} search for ${targetItem || "black size 10 boots"}${targetLocation ? ` at ${targetLocation}` : ""}.`,
        evidenceLabel: "What proof should come back?",
        evidenceHelp: "Write the evidence you expect if the search succeeds or fails. Comma-separated is fine. Do not use snake_case.",
        evidenceExamples: [
          `${residentName} reports whether ${targetItem || "the item"} was found`,
          `${residentName} says where they looked`,
          `${residentName} describes one concrete clue or obstacle`,
        ],
      };
    case "deliver_message":
      return {
        summary: "Use this when the resident should get a message to a specific person.",
        required: ["Target person"],
        example: `Example task: ask ${residentName} to deliver a message to ${targetPerson || "Lars Jensen"}.`,
        evidenceLabel: "What proof would convince you the delivery happened?",
        evidenceHelp: "Write plain-language delivery evidence. Comma-separated is fine. Do not use snake_case.",
        evidenceExamples: [
          `${targetPerson || "The recipient"} acknowledges the message`,
          `${residentName} reports when or how delivery happened`,
          `${residentName} relays any response they received`,
        ],
      };
    default:
      return {
        summary: "Open-ended quests are looser and rely more on prose. Use structured modes when you can.",
        required: [],
        example: `Example task: give ${residentName} a clear brief with explicit proof expectations.`,
        evidenceLabel: "What proof should come back?",
        evidenceHelp: "For open briefs, evidence matters even more. Write plain-language proof expectations, separated by commas.",
        evidenceExamples: [
          `${residentName} reports what they did`,
          `${residentName} names who or what they encountered`,
          `${residentName} confirms one concrete outcome`,
        ],
      };
  }
}

const QUEST_PATTERN_OPTIONS: QuestPatternOption[] = [
  {
    objectiveType: "meet_person",
    label: "Introduce",
    description: "Send someone into a real meeting with another member at a known place.",
  },
  {
    objectiveType: "speak_with_person",
    label: "Reach Out",
    description: "Prompt a direct conversation or correspondence with a known person.",
  },
  {
    objectiveType: "observe_location",
    label: "Scout",
    description: "Ask for grounded observation and reporting from a specific place.",
  },
  {
    objectiveType: "visit_location",
    label: "Send Somewhere",
    description: "Create a reason to go somewhere real in the city.",
  },
  {
    objectiveType: "deliver_message",
    label: "Deliver",
    description: "Use a concrete message or handoff to create accountable follow-through.",
  },
  {
    objectiveType: "find_item",
    label: "Search",
    description: "Give them a specific thing to look for in the world.",
  },
  {
    objectiveType: "open_ended",
    label: "Open Brief",
    description: "Use prose when the task needs more room than the structured objective types.",
  },
];

function buildQuestTitle(params: {
  objectiveType: string;
  targetLocation: string;
  targetPerson: string;
  targetItem: string;
  residentName?: string;
}): string {
  const objectiveType = String(params.objectiveType || "").trim();
  const targetLocation = String(params.targetLocation || "").trim();
  const targetPerson = String(params.targetPerson || "").trim();
  const targetItem = String(params.targetItem || "").trim();
  const residentName = String(params.residentName || "").trim();

  if (objectiveType === "meet_person" && targetPerson && targetLocation) return `Meet ${targetPerson} at ${targetLocation}`;
  if (objectiveType === "meet_person" && targetPerson) return `Meet ${targetPerson}`;
  if (objectiveType === "speak_with_person" && targetPerson) return `Reach ${targetPerson}`;
  if (objectiveType === "observe_location" && targetLocation) return `Observe ${targetLocation}`;
  if (objectiveType === "visit_location" && targetLocation) return `Go to ${targetLocation}`;
  if (objectiveType === "deliver_message" && targetPerson) return `Deliver message to ${targetPerson}`;
  if (objectiveType === "find_item" && targetItem) return `Find ${targetItem}`;
  if (residentName) return `New quest for ${residentName}`;
  return "New guild quest";
}

function containsConcreteTarget(params: {
  objectiveType: string;
  targetLocation: string;
  targetPerson: string;
  targetItem: string;
}): boolean {
  return Boolean(
    String(params.targetLocation || "").trim()
    || String(params.targetPerson || "").trim()
    || String(params.targetItem || "").trim()
    || String(params.objectiveType || "").trim() !== "open_ended",
  );
}

function buildQuestRubric(params: {
  objectiveType: string;
  brief: string;
  targetLocation: string;
  targetPerson: string;
  targetItem: string;
  successSignals: string;
  selectedResident: GuildBoardMember | null;
}): QuestRubricItem[] {
  const objectiveType = String(params.objectiveType || "").trim();
  const brief = String(params.brief || "").trim();
  const targetLocation = String(params.targetLocation || "").trim();
  const targetPerson = String(params.targetPerson || "").trim();
  const targetItem = String(params.targetItem || "").trim();
  const residentLocation = String(params.selectedResident?.location || "").trim();
  const signalList = String(params.successSignals || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

  let scattering: QuestRubricItem;
  if (targetLocation && residentLocation && targetLocation.toLowerCase() !== residentLocation.toLowerCase()) {
    scattering = {
      label: "Scattering pressure",
      strength: "strong",
      summary: `This quest pulls ${params.selectedResident?.display_name ?? "the target"} away from ${residentLocation.replace(/_/g, " ")} toward ${targetLocation}.`,
      prompt: "Keep naming real places, new contacts, or institutions so the task breaks local clustering.",
    };
  } else if ((objectiveType === "speak_with_person" || objectiveType === "deliver_message") && targetPerson) {
    scattering = {
      label: "Scattering pressure",
      strength: "strong",
      summary: `This quest creates direct cross-contact with ${targetPerson}, even without forcing travel.`,
      prompt: "Add a location only if you also want to push movement through the world, not just contact.",
    };
  } else if (objectiveType === "meet_person" && targetPerson && targetLocation) {
    scattering = {
      label: "Scattering pressure",
      strength: "strong",
      summary: `This quest creates both contact with ${targetPerson} and movement toward ${targetLocation}.`,
      prompt: "This is the clearest anti-echo pattern: real contact plus a real place.",
    };
  } else if (targetLocation || targetPerson) {
    scattering = {
      label: "Scattering pressure",
      strength: "developing",
      summary: "This quest introduces at least one concrete target, but it may still stay within the target's current basin.",
      prompt: "If possible, add a place, person, or institution that widens who they meet or where they go.",
    };
  } else {
    scattering = {
      label: "Scattering pressure",
      strength: "weak",
      summary: "Right now this could likely be completed without leaving the current social loop.",
      prompt: "Name a real destination, person, or institution that creates genuine movement or cross-contact.",
    };
  }

  let evidence: QuestRubricItem;
  if (signalList.length >= 2) {
    evidence = {
      label: "Evidence shape",
      strength: "strong",
      summary: "Success has multiple visible signals, which makes review and follow-through much easier.",
      prompt: "Keep signals concrete: who was met, what was observed, what was delivered, what changed.",
    };
  } else if (signalList.length === 1 || objectiveType !== "open_ended") {
    evidence = {
      label: "Evidence shape",
      strength: "developing",
      summary: "The quest is assignable, but the reviewer still needs clearer proof to look for after it runs.",
      prompt: "Add one or two plain-language signals such as a reply, report, delivery, meeting, or observation.",
    };
  } else {
    evidence = {
      label: "Evidence shape",
      strength: "weak",
      summary: "Success is still too implicit. A reviewer may only know that a vibe happened.",
      prompt: "Name what would count as proof: a meeting, observation, delivery, confirmation, or reported detail.",
    };
  }

  const concreteTarget = containsConcreteTarget({ objectiveType, targetLocation, targetPerson, targetItem });
  let grounding: QuestRubricItem;
  if (brief.length >= 120 && concreteTarget) {
    grounding = {
      label: "Grounding quality",
      strength: "strong",
      summary: "The task has concrete anchors and enough detail to resist drifting into generic atmosphere.",
      prompt: "Keep the brief practical and specific about what they should do, notice, or verify.",
    };
  } else if (brief.length >= 60 || concreteTarget) {
    grounding = {
      label: "Grounding quality",
      strength: "developing",
      summary: "The quest has some grounded detail, but parts of it could still blur into open-ended mood play.",
      prompt: "Add exact places, people, items, or observable actions to make the task harder to fake.",
    };
  } else {
    grounding = {
      label: "Grounding quality",
      strength: "weak",
      summary: "The quest is still too abstract to reliably generate distinct, checkable behavior.",
      prompt: "Replace atmosphere with specifics: where, who, what, and what evidence should come back.",
    };
  }

  return [scattering, evidence, grounding];
}

function templateShowsLocation(objectiveType: string): boolean {
  return ["visit_location", "observe_location", "meet_person", "find_item"].includes(String(objectiveType || "").trim());
}

function templateRequiresLocation(objectiveType: string): boolean {
  return ["visit_location", "observe_location", "meet_person"].includes(String(objectiveType || "").trim());
}

function templateShowsPerson(objectiveType: string): boolean {
  return ["speak_with_person", "meet_person", "deliver_message"].includes(String(objectiveType || "").trim());
}

function templateRequiresPerson(objectiveType: string): boolean {
  return ["speak_with_person", "meet_person", "deliver_message"].includes(String(objectiveType || "").trim());
}

function templateShowsItem(objectiveType: string): boolean {
  return String(objectiveType || "").trim() === "find_item";
}

export function GuildBoard({
  board,
  pending = false,
  error,
  onRefresh,
  onAssignQuest,
  onIssueStarterPack,
  onBootstrapSteward,
  onPatchMemberProfile,
}: GuildBoardProps) {
  const [targetActorId, setTargetActorId] = useState("");
  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [branch, setBranch] = useState("");
  const [questBand, setQuestBand] = useState("");
  const [objectiveType, setObjectiveType] = useState("open_ended");
  const [targetLocation, setTargetLocation] = useState("");
  const [targetPerson, setTargetPerson] = useState("");
  const [targetItem, setTargetItem] = useState("");
  const [successSignals, setSuccessSignals] = useState("");
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
    () => allMembers.find((member) => member.actor_id === targetActorId) ?? null,
    [allMembers, targetActorId],
  );
  const selectedMember = useMemo(
    () => allMembers.find((member) => member.actor_id === memberActorId) ?? null,
    [allMembers, memberActorId],
  );
  const selectedPattern = useMemo(
    () => QUEST_PATTERN_OPTIONS.find((option) => option.objectiveType === objectiveType) ?? QUEST_PATTERN_OPTIONS[QUEST_PATTERN_OPTIONS.length - 1],
    [objectiveType],
  );
  const selectedStarterPack = useMemo(
    () => starterPackMeta(selectedResident),
    [selectedResident],
  );
  const eligibleStarterMembers = useMemo(
    () => allMembers.filter((member) => member.rank === "apprentice" && !starterPackMeta(member)),
    [allMembers],
  );
  const trimmedTargetLocation = targetLocation.trim();
  const trimmedTargetPerson = targetPerson.trim();
  const trimmedTargetItem = targetItem.trim();
  const rubricItems = useMemo(
    () => buildQuestRubric({
      objectiveType,
      brief,
      targetLocation: trimmedTargetLocation,
      targetPerson: trimmedTargetPerson,
      targetItem: trimmedTargetItem,
      successSignals,
      selectedResident,
    }),
    [brief, objectiveType, selectedResident, successSignals, trimmedTargetItem, trimmedTargetLocation, trimmedTargetPerson],
  );
  const questHelp = useMemo(
    () => objectiveGuidance({
      objectiveType,
      targetPerson: trimmedTargetPerson,
      targetLocation: trimmedTargetLocation,
      targetItem: trimmedTargetItem,
      selectedResident,
    }),
    [objectiveType, selectedResident, trimmedTargetItem, trimmedTargetLocation, trimmedTargetPerson],
  );
  const resolvedQuestTitle = title.trim() || buildQuestTitle({
    objectiveType,
    targetLocation: trimmedTargetLocation,
    targetPerson: trimmedTargetPerson,
    targetItem: trimmedTargetItem,
    residentName: selectedResident?.display_name,
  });
  const missingQuestFields = [
    ...(objectiveType === "visit_location" || objectiveType === "observe_location" || objectiveType === "meet_person"
      ? (!trimmedTargetLocation ? ["Target location"] : [])
      : []),
    ...(objectiveType === "speak_with_person" || objectiveType === "meet_person" || objectiveType === "deliver_message"
      ? (!trimmedTargetPerson ? ["Target person"] : [])
      : []),
    ...(objectiveType === "find_item"
      ? (!trimmedTargetItem ? ["Target item"] : [])
      : []),
  ];
  const canSubmitQuest = Boolean(
    canAssignQuests &&
    !pending &&
    targetActorId &&
    resolvedQuestTitle &&
    missingQuestFields.length === 0
  );
  const showLocationField = templateShowsLocation(objectiveType);
  const showPersonField = templateShowsPerson(objectiveType);
  const showItemField = templateShowsItem(objectiveType);
  const requiredLocation = templateRequiresLocation(objectiveType);
  const requiredPerson = templateRequiresPerson(objectiveType);
  const topFieldCount = (showLocationField ? 1 : 0) + (showPersonField ? 1 : 0);
  const canIssueStarterToSelected = Boolean(
    canAssignQuests &&
    !pending &&
    selectedResident &&
    selectedResident.rank === "apprentice" &&
    !selectedStarterPack,
  );
  const canIssueStarterBulk = Boolean(canAssignQuests && !pending && eligibleStarterMembers.length > 0);

  function addSuccessSignalExample(example: string) {
    const next = example.trim();
    if (!next) return;
    const existing = successSignals
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (existing.some((item) => item.toLowerCase() === next.toLowerCase())) return;
    setSuccessSignals(existing.length > 0 ? `${existing.join(", ")}, ${next}` : next);
  }

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
    if (!canSubmitQuest) return;
    await onAssignQuest({
      target_actor_id: targetActorId,
      title: resolvedQuestTitle,
      brief: brief.trim(),
      branch: branch.trim() || undefined,
      quest_band: questBand.trim() || undefined,
      objective_type: objectiveType.trim() || undefined,
      target_location: targetLocation.trim() || undefined,
      target_person: targetPerson.trim() || undefined,
      target_item: targetItem.trim() || undefined,
      success_signals: successSignals
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    });
    setTitle("");
    setBrief("");
    setBranch("");
    setQuestBand("");
    setObjectiveType("open_ended");
    setTargetLocation("");
    setTargetPerson("");
    setTargetItem("");
    setSuccessSignals("");
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

  async function issueStarterPackToSelected() {
    if (!selectedResident || !canIssueStarterToSelected) return;
    await onIssueStarterPack({ target_actor_id: selectedResident.actor_id });
  }

  async function issueStarterPackToAllEligible() {
    if (!canIssueStarterBulk) return;
    await onIssueStarterPack();
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
            No guild steward has been labeled yet. Claiming this threshold unlocks the advanced governance layer so someone can maintain the board, member roles, and shard-level guild responsibilities.
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
        <div style={{ fontWeight: 700, marginBottom: "0.4rem" }}>Contribution Workspace</div>
        <div style={{ fontSize: "0.92rem", opacity: 0.85, marginBottom: "0.75rem" }}>
          {canAssignQuests
            ? "Start with one useful quest. Use the guided workspace first; the raw structured form remains below for direct control."
            : "Your current guild role can review the board, but higher-trust quest assignment is still locked."}
        </div>
        <div className="ww-guild-guide-grid">
          {QUEST_PATTERN_OPTIONS.map((option) => (
            <button
              key={option.objectiveType}
              type="button"
              className={`ww-guild-guide-card${objectiveType === option.objectiveType ? " ww-guild-guide-card--active" : ""}`}
              onClick={() => setObjectiveType(option.objectiveType)}
              disabled={!canAssignQuests || pending}
            >
              <span className="ww-guild-guide-card-title">{option.label}</span>
              <span className="ww-guild-guide-card-copy">{option.description}</span>
            </button>
          ))}
        </div>
        <div className="ww-guild-guide-note">
          <div className="ww-guild-guide-note-title">
            Guided path: {selectedPattern.label}
          </div>
          <div>{questHelp.summary}</div>
          {questHelp.required.length > 0 && (
            <div style={{ marginTop: "0.25rem" }}>
              Required: {questHelp.required.join(" · ")}
            </div>
          )}
          <div style={{ marginTop: "0.25rem", opacity: 0.78 }}>{questHelp.example}</div>
        </div>
        <div style={{ display: "grid", gap: "0.75rem" }}>
          <label style={{ display: "grid", gap: "0.3rem" }}>
            <span style={{ fontSize: "0.84rem", opacity: 0.8 }}>Who is this for?</span>
          <select
            className="ww-chat-input"
            value={targetActorId}
            onChange={(e) => setTargetActorId(e.target.value)}
            disabled={!canAssignQuests || pending}
          >
            <option value="">Choose a guild member…</option>
            {allMembers
              .filter((member) => member.actor_id !== me?.actor_id)
              .map((member) => (
              <option key={member.actor_id} value={member.actor_id}>
                {residentLabel(member)}
              </option>
            ))}
          </select>
          </label>
          <div className="ww-guild-guide-note" style={{ marginBottom: 0 }}>
            <div className="ww-guild-guide-note-title">Starter track</div>
            <div>
              Seed apprentices with a small foundations pack instead of writing every first quest by hand. The current pack issues grounded observation, direct contact, and movement-oriented work when the world has enough context.
            </div>
            <div style={{ marginTop: "0.35rem", fontSize: "0.88rem", opacity: 0.84 }}>
              Eligible apprentices right now: {eligibleStarterMembers.length}
            </div>
            {selectedResident && (
              <div style={{ marginTop: "0.35rem", fontSize: "0.88rem", opacity: 0.9 }}>
                {selectedStarterPack
                  ? `${selectedResident.display_name} already has a starter pack (${String(selectedStarterPack.quest_count ?? 0)} quests).`
                  : selectedResident.rank !== "apprentice"
                    ? `${selectedResident.display_name} is ${selectedResident.rank.replace(/_/g, " ")}, so the starter pack is not the default fit.`
                    : `${selectedResident.display_name} is eligible for the starter pack.`}
              </div>
            )}
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.65rem" }}>
              <button
                className="ww-send-btn"
                type="button"
                onClick={() => void issueStarterPackToSelected()}
                disabled={!canIssueStarterToSelected}
                style={{ width: "fit-content" }}
              >
                {pending ? "Issuing..." : selectedResident ? `Issue starter pack to ${selectedResident.display_name}` : "Select an apprentice first"}
              </button>
              <button
                className="ww-recovery-strip-btn"
                type="button"
                onClick={() => void issueStarterPackToAllEligible()}
                disabled={!canIssueStarterBulk}
              >
                {pending ? "Issuing..." : `Issue starter packs to all eligible (${eligibleStarterMembers.length})`}
              </button>
            </div>
          </div>
          <label style={{ display: "grid", gap: "0.3rem" }}>
            <span style={{ fontSize: "0.84rem", opacity: 0.8 }}>What should happen?</span>
          <textarea
            className="ww-notes-area"
            rows={4}
            placeholder="Describe the task in plain language. What should they notice, verify, deliver, repair, or complete?"
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            disabled={!canAssignQuests || pending}
            style={{ minHeight: "7rem" }}
          />
          </label>
          {topFieldCount > 0 && (
            <div style={{ display: "grid", gridTemplateColumns: topFieldCount > 1 ? "1fr 1fr" : "1fr", gap: "0.65rem" }}>
              {showLocationField && (
                <label style={{ display: "grid", gap: "0.3rem" }}>
                  <span style={{ fontSize: "0.84rem", opacity: 0.8 }}>
                    Target location
                    {requiredLocation ? " · required" : " · optional"}
                  </span>
                  <input
                    className="ww-chat-input"
                    type="text"
                    placeholder={objectiveType === "find_item" ? "Optional: where the search should happen" : "Exact known place name"}
                    value={targetLocation}
                    onChange={(e) => setTargetLocation(e.target.value)}
                    disabled={!canAssignQuests || pending}
                  />
                </label>
              )}
              {showPersonField && (
                <label style={{ display: "grid", gap: "0.3rem" }}>
                  <span style={{ fontSize: "0.84rem", opacity: 0.8 }}>
                    Target person
                    {requiredPerson ? " · required" : " · optional"}
                  </span>
                  <select
                    className="ww-chat-input"
                    value={targetPerson}
                    onChange={(e) => setTargetPerson(e.target.value)}
                    disabled={!canAssignQuests || pending}
                  >
                    <option value="">Choose a known member…</option>
                    {allMembers
                      .filter((member) => member.actor_id !== targetActorId)
                      .map((member) => (
                        <option key={`target-person-${member.actor_id}`} value={member.display_name}>
                          {member.display_name} · {member.member_type}
                        </option>
                      ))}
                  </select>
                </label>
              )}
            </div>
          )}
          {showItemField && (
            <label style={{ display: "grid", gap: "0.3rem" }}>
              <span style={{ fontSize: "0.84rem", opacity: 0.8 }}>Target item · required</span>
              <input
                className="ww-chat-input"
                type="text"
                placeholder="Concrete item to look for"
                value={targetItem}
                onChange={(e) => setTargetItem(e.target.value)}
                disabled={!canAssignQuests || pending}
              />
            </label>
          )}
          <label style={{ display: "grid", gap: "0.3rem" }}>
            <span style={{ fontSize: "0.84rem", opacity: 0.8 }}>{questHelp.evidenceLabel}</span>
          <input
            className="ww-chat-input"
            type="text"
            placeholder={questHelp.evidenceExamples.join(", ")}
            value={successSignals}
            onChange={(e) => setSuccessSignals(e.target.value)}
            disabled={!canAssignQuests || pending}
          />
          </label>
          <div className="ww-guild-evidence-help">
            <div className="ww-guild-evidence-help-title">Review guide</div>
            <div className="ww-guild-evidence-help-copy">{questHelp.evidenceHelp}</div>
            <div className="ww-guild-evidence-chip-row">
              {questHelp.evidenceExamples.map((example) => (
                <button
                  key={example}
                  type="button"
                  className="ww-guild-evidence-chip"
                  onClick={() => addSuccessSignalExample(example)}
                  disabled={!canAssignQuests || pending}
                >
                  + {example}
                </button>
              ))}
            </div>
          </div>
          <div className="ww-guild-rubric">
            <div className="ww-guild-rubric-header">
              <div className="ww-guild-rubric-title">Quest quality rubric</div>
              <div className="ww-guild-rubric-copy">
                Use this as a drafting aid. "Developing" does not mean the quest is bad. It means the draft is usable but still has one obvious way to become easier to review or better at breaking echo loops.
              </div>
            </div>
            <div className="ww-guild-rubric-grid">
              {rubricItems.map((item) => (
                <div key={item.label} className={`ww-guild-rubric-card ww-guild-rubric-card--${item.strength}`}>
                  <div className="ww-guild-rubric-card-head">
                    <span className="ww-guild-rubric-card-title">{item.label}</span>
                    <span className={`ww-guild-rubric-pill ww-guild-rubric-pill--${item.strength}`}>
                      {item.strength}
                    </span>
                  </div>
                  <div className="ww-guild-rubric-summary">{item.summary}</div>
                  <div className="ww-guild-rubric-prompt">{item.prompt}</div>
                </div>
              ))}
            </div>
          </div>
          <label style={{ display: "grid", gap: "0.3rem" }}>
            <span style={{ fontSize: "0.84rem", opacity: 0.8 }}>Quest title override</span>
          <input
            className="ww-chat-input"
            type="text"
            placeholder={resolvedQuestTitle}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            disabled={!canAssignQuests || pending}
          />
          </label>
          {missingQuestFields.length > 0 && (
            <div style={{ fontSize: "0.84rem", color: "var(--ww-error, #d46b6b)" }}>
              Missing for this objective: {missingQuestFields.join(" · ")}
            </div>
          )}
          {selectedResident && (
            <div className="ww-guild-guide-note" style={{ marginBottom: 0 }}>
              <div className="ww-guild-guide-note-title">Ready to assign</div>
              <div style={{ fontSize: "0.88rem", opacity: 0.9 }}>
                <strong>{resolvedQuestTitle}</strong>
              </div>
              <div style={{ fontSize: "0.88rem", opacity: 0.85, marginTop: "0.25rem" }}>
                Target: {selectedResident.display_name}
                {selectedResident.member_type ? ` · ${selectedResident.member_type}` : ""}
                {selectedResident.location ? ` · ${selectedResident.location.replace(/_/g, " ")}` : ""}
                {selectedResident.branches.length > 0 ? ` · ${selectedResident.branches.join(", ")}` : ""}
              </div>
            </div>
          )}
          <button
            className="ww-send-btn"
            onClick={() => void submitQuest()}
            disabled={!canSubmitQuest}
            style={{ width: "fit-content", minWidth: "8rem" }}
            title={missingQuestFields.length > 0 ? `Missing: ${missingQuestFields.join(", ")}` : ""}
          >
            {pending ? "Assigning..." : "Assign Quest"}
          </button>
          <details className="ww-guild-advanced">
            <summary>Advanced form and structured fields</summary>
            <div className="ww-guild-guide-note" style={{ marginTop: "0.85rem" }}>
              <div className="ww-guild-guide-note-title">
                Objective guide: {objectiveType.replace(/_/g, " ")}
              </div>
              <div>{questHelp.summary}</div>
              {questHelp.required.length > 0 && (
                <div style={{ marginTop: "0.25rem" }}>
                  Required: {questHelp.required.join(" · ")}
                </div>
              )}
              <div style={{ marginTop: "0.25rem", opacity: 0.78 }}>{questHelp.example}</div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.65rem", marginTop: "0.85rem" }}>
              <label style={{ display: "grid", gap: "0.3rem" }}>
                <span style={{ fontSize: "0.84rem", opacity: 0.8 }}>Objective type</span>
              <select
                className="ww-chat-input"
                value={objectiveType}
                onChange={(e) => setObjectiveType(e.target.value)}
                disabled={!canAssignQuests || pending}
              >
                {QUEST_PATTERN_OPTIONS.map((option) => (
                  <option key={option.objectiveType} value={option.objectiveType}>
                    {option.objectiveType.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
              </label>
              <label style={{ display: "grid", gap: "0.3rem" }}>
                <span style={{ fontSize: "0.84rem", opacity: 0.8 }}>Branch</span>
              <input
                className="ww-chat-input"
                type="text"
                placeholder="Branch"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                disabled={!canAssignQuests || pending}
              />
              </label>
              <label style={{ display: "grid", gap: "0.3rem" }}>
                <span style={{ fontSize: "0.84rem", opacity: 0.8 }}>Quest band</span>
                <input
                  className="ww-chat-input"
                  type="text"
                  placeholder="Quest band"
                  value={questBand}
                  onChange={(e) => setQuestBand(e.target.value)}
                  disabled={!canAssignQuests || pending}
                />
              </label>
            </div>
          </details>
        </div>
      </section>

      <section className="ww-info-card" style={{ border: "1px solid var(--ww-border)", borderRadius: "8px", padding: "1rem" }}>
        <div style={{ fontWeight: 700, marginBottom: "0.4rem" }}>Steward Tools</div>
        <div style={{ fontSize: "0.92rem", opacity: 0.85, marginBottom: "0.75rem" }}>
          {canManageRoles
            ? "Tune guild rank, branches, and advanced roles for members who have already shown useful contribution."
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
              {starterPackMeta(human) && (
                <div style={{ fontSize: "0.82rem", opacity: 0.72, marginTop: "0.15rem" }}>
                  starter pack issued · {String(starterPackMeta(human)?.quest_count ?? 0)} quests
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
              {starterPackMeta(resident) && (
                <div style={{ fontSize: "0.82rem", opacity: 0.72, marginTop: "0.15rem" }}>
                  starter pack issued · {String(starterPackMeta(resident)?.quest_count ?? 0)} quests
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
                {questObjectiveSummary(quest) && (
                  <div style={{ fontSize: "0.9rem", marginTop: "0.25rem" }}>
                    <strong>Objective:</strong> {questObjectiveSummary(quest)}
                  </div>
                )}
                {Array.isArray(quest.success_signals) && quest.success_signals.length > 0 && (
                  <div style={{ fontSize: "0.84rem", marginTop: "0.2rem", opacity: 0.8 }}>
                    Signals: {quest.success_signals.join(" · ")}
                  </div>
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
                {questObjectiveSummary(quest) && (
                  <div style={{ fontSize: "0.9rem", marginTop: "0.25rem" }}>
                    <strong>Objective:</strong> {questObjectiveSummary(quest)}
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
