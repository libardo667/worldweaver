import type { ReactNode, RefObject } from "react";

import type { DMRecipient, DMThread, InboxDM, LocationChatEntry, LocationGraphNode, RestMetricsResponse } from "../api/wwClient";
import type { GuildBoardResponse, GuildQuestRecord } from "../types";
import { GuildBoard } from "./GuildBoard";
import { GuildQuestPanel } from "./GuildQuestPanel";
import { LetterCompose } from "./LetterCompose";
import { LocationMap } from "./LocationMap";
import { PresencePanel } from "./PresencePanel";

type WorldInfoPaneProps = {
  isMobile: boolean;
  isInfoPaneCollapsed: boolean;
  leftWidth: number;
  observerMode: boolean;
  infoTab: "map" | "presence" | "chats" | "notes" | "guild";
  setInfoTab: (tab: "map" | "presence" | "chats" | "notes" | "guild") => void;
  chatsTabHasUnread: boolean;
  onCollapse: () => void;
  chatSubtabs: Array<"dms" | "local" | "city" | "global">;
  chatSubTab: "dms" | "local" | "city" | "global";
  setChatSubTab: (tab: "dms" | "local" | "city" | "global") => void;
  chatUnread: Record<"dms" | "local" | "city" | "global", boolean>;
  rosterDigest: {
    roster: Array<{ session_id: string; display_name?: string | null; player_name?: string | null; status?: string | null }>;
    active_sessions: number;
  } | null;
  sessionId: string;
  observerHereNames: string[];
  currentViewLocation: string;
  chatMessages: LocationChatEntry[];
  chatEndRef: RefObject<HTMLDivElement | null>;
  chatInput: string;
  setChatInput: (value: string) => void;
  sendChat: () => void;
  chatPending: boolean;
  localMentionPreview: ReactNode;
  cityMessages: LocationChatEntry[];
  cityEndRef: RefObject<HTMLDivElement | null>;
  cityInput: string;
  setCityInput: (value: string) => void;
  sendCityChat: () => void;
  cityPending: boolean;
  cityMentionPreview: ReactNode;
  globalMessages: LocationChatEntry[];
  globalEndRef: RefObject<HTMLDivElement | null>;
  globalInput: string;
  setGlobalInput: (value: string) => void;
  sendGlobalChat: () => void;
  globalPending: boolean;
  globalMentionPreview: ReactNode;
  playerName?: string;
  dmRecipients: DMRecipient[];
  preferredRecipientKey?: string;
  sessionInboxId: string;
  onMessageSent: (sent: { recipientKey: string; recipientLabel: string; body: string; dmId: number }) => void;
  refreshInbox: () => void;
  playerThreads: DMThread[];
  selectedThreadKey: string | null;
  openPlayerThread: (thread: DMThread) => void;
  playerInbox: InboxDM[];
  mapSearch: string;
  setMapSearch: (value: string) => void;
  mapFilter: "all" | "occupied" | "quiet" | "landmarks";
  setMapFilter: (filter: "all" | "occupied" | "quiet" | "landmarks") => void;
  mapPending: boolean;
  displayMapNodes: LocationGraphNode[];
  mapEdges: Array<{ from: string; to: string }>;
  showingEntryScreen: boolean;
  pending: boolean;
  handleMapNodeClick?: (nodeName: string) => void;
  pendingDest: string | null;
  confirmRouteMove: () => void;
  clearPendingDest: () => void;
  pendingPath: string[];
  setMapViewport: (viewport: { north: number; south: number; east: number; west: number }) => void;
  restMetrics: RestMetricsResponse | null;
  refreshRestMetrics: () => void;
  canUseMentorBoard: boolean;
  guildBoard: GuildBoardResponse | null;
  guildBoardPending: boolean;
  guildBoardError: string | null;
  refreshGuildBoard: () => void;
  assignQuest: (payload: Parameters<NonNullable<React.ComponentProps<typeof GuildBoard>["onAssignQuest"]>>[0]) => Promise<void>;
  issueStarterPacks: (payload?: Parameters<NonNullable<React.ComponentProps<typeof GuildBoard>["onIssueStarterPack"]>>[0]) => Promise<void>;
  resetStarterPacks: (payload?: Parameters<NonNullable<React.ComponentProps<typeof GuildBoard>["onResetStarterPack"]>>[0]) => Promise<void>;
  bootstrapSteward: () => Promise<void>;
  patchMemberProfile: (payload: Parameters<NonNullable<React.ComponentProps<typeof GuildBoard>["onPatchMemberProfile"]>>[0]) => Promise<void>;
  guildQuests: GuildQuestRecord[];
  guildQuestsPending: boolean;
  guildQuestsError: string | null;
  refreshGuildQuests: () => void;
  playerNotes: string;
  setPlayerNotes: (value: string) => void;
};

export function WorldInfoPane({
  isMobile,
  isInfoPaneCollapsed,
  leftWidth,
  observerMode,
  infoTab,
  setInfoTab,
  chatsTabHasUnread,
  onCollapse,
  chatSubtabs,
  chatSubTab,
  setChatSubTab,
  chatUnread,
  rosterDigest,
  sessionId,
  observerHereNames,
  currentViewLocation,
  chatMessages,
  chatEndRef,
  chatInput,
  setChatInput,
  sendChat,
  chatPending,
  localMentionPreview,
  cityMessages,
  cityEndRef,
  cityInput,
  setCityInput,
  sendCityChat,
  cityPending,
  cityMentionPreview,
  globalMessages,
  globalEndRef,
  globalInput,
  setGlobalInput,
  sendGlobalChat,
  globalPending,
  globalMentionPreview,
  playerName,
  dmRecipients,
  preferredRecipientKey,
  sessionInboxId,
  onMessageSent,
  refreshInbox,
  playerThreads,
  selectedThreadKey,
  openPlayerThread,
  playerInbox,
  mapSearch,
  setMapSearch,
  mapFilter,
  setMapFilter,
  mapPending,
  displayMapNodes,
  mapEdges,
  showingEntryScreen,
  pending,
  handleMapNodeClick,
  pendingDest,
  confirmRouteMove,
  clearPendingDest,
  pendingPath,
  setMapViewport,
  restMetrics,
  refreshRestMetrics,
  canUseMentorBoard,
  guildBoard,
  guildBoardPending,
  guildBoardError,
  refreshGuildBoard,
  assignQuest,
  issueStarterPacks,
  resetStarterPacks,
  bootstrapSteward,
  patchMemberProfile,
  guildQuests,
  guildQuestsPending,
  guildQuestsError,
  refreshGuildQuests,
  playerNotes,
  setPlayerNotes,
}: WorldInfoPaneProps) {
  const persistentPanelStyle = (visible: boolean): React.CSSProperties => ({
    display: "flex",
    flexDirection: "column",
    height: "100%",
    ...(visible
      ? {
          position: "relative",
          visibility: "visible",
          pointerEvents: "auto",
        }
      : {
          position: "absolute",
          inset: 0,
          visibility: "hidden",
          pointerEvents: "none",
          overflow: "hidden",
        }),
  });

  if (!isMobile && isInfoPaneCollapsed) {
    return (
      <div className="ww-expand-bar" onClick={onCollapse} title="Expand Info">
        INFO TAB ◀
      </div>
    );
  }

  return (
    <div
      className={`ww-info-pane${isMobile ? " ww-info-pane--mobile" : " ww-info-pane--desktop"}`}
      style={
        isMobile
          ? undefined
          : {
              width: `${100 - leftWidth}%`,
              flex: `0 0 ${100 - leftWidth}%`,
            }
      }
    >
      <div className="ww-info-tabs">
        <div className="ww-info-tabs-list">
          {([
            "map",
            ...((!observerMode) ? (["guild"] as const) : []),
            "presence",
            "chats",
            "notes",
          ] as const).map((tab) => (
            <button
              key={tab}
              className={`ww-info-tab${infoTab === tab ? " ww-info-tab--active" : ""}`}
              onClick={() => setInfoTab(tab)}
            >
              <span className="ww-tab-label">
                {tab === "guild" ? "Guild" : tab.charAt(0).toUpperCase() + tab.slice(1)}
                {tab === "chats" && chatsTabHasUnread && <span className="ww-tab-dot" aria-hidden="true" />}
              </span>
            </button>
          ))}
        </div>
        {!isMobile && (
          <button className="ww-collapse-btn" onClick={onCollapse} title="Collapse Info">
            ▶
          </button>
        )}
      </div>

      <div className="ww-info-body" style={{ flex: 1, overflowY: "auto", position: "relative" }}>
        {infoTab === "chats" && (
          <div className="ww-chats-container" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
            <div className="ww-chat-subtabs">
              {chatSubtabs.map((sub) => (
                <button
                  key={sub}
                  className={`ww-chat-subtab${chatSubTab === sub ? " ww-chat-subtab--active" : ""}`}
                  onClick={() => setChatSubTab(sub)}
                >
                  <span className="ww-tab-label">
                    {sub === "dms" ? "DMs" : sub.charAt(0).toUpperCase() + sub.slice(1)}
                    {chatUnread[sub] && <span className="ww-tab-dot" aria-hidden="true" />}
                  </span>
                </button>
              ))}
            </div>

            {chatSubTab === "local" && (
              <div className="ww-here-container" style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
                {!observerMode && rosterDigest?.roster && rosterDigest.roster.length > 0 && (
                  <details className="ww-here-roster-collapsible" style={{ borderBottom: "1px solid var(--ww-border)" }}>
                    <summary style={{ padding: "0.5rem 1rem", cursor: "pointer", fontWeight: 600, backgroundColor: "var(--ww-bg-accent)", borderBottom: "1px solid var(--ww-border)" }}>
                      Inhabitants ({rosterDigest.active_sessions} active / {rosterDigest.roster.length} present)
                    </summary>
                    <div className="ww-here-roster" style={{ padding: "1rem", display: "flex", flexDirection: "column", alignItems: "center", maxHeight: "40vh", overflowY: "auto" }}>
                      <ul className="ww-roster" style={{ width: "100%", listStyle: "none", padding: 0 }}>
                        {rosterDigest.roster.map((r) => (
                          <li
                            key={r.session_id}
                            className={`ww-roster-entry${r.session_id === sessionId ? " ww-roster-entry--you" : ""}`}
                            style={{ padding: "0.75rem", marginBottom: "0.5rem", backgroundColor: "var(--ww-bg-accent, #1a1a1a)", borderRadius: "4px", border: "1px solid var(--ww-border)", width: "100%", textAlign: "center" }}
                          >
                            <div className="ww-roster-card-line">
                              <span className="ww-roster-name" style={{ fontWeight: 600 }}>
                                {r.display_name ?? r.player_name ?? r.session_id.slice(0, 12)}
                                {r.session_id === sessionId && <span className="ww-roster-you"> (you)</span>}
                              </span>
                              <div className="ww-presence-chips">
                                {r.status && (
                                  <span className={`ww-presence-pill ww-presence-pill--${r.status}`}>
                                    {r.status === "resting" ? "Resting" : r.status === "returning" ? "Returning" : "Active"}
                                  </span>
                                )}
                              </div>
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </details>
                )}
                {observerMode && currentViewLocation && (
                  <div className="ww-here-roster-collapsible" style={{ borderBottom: "1px solid var(--ww-border)", padding: "0.75rem 1rem" }}>
                    <div style={{ fontWeight: 600, marginBottom: "0.35rem" }}>
                      Observed here ({observerHereNames.length})
                    </div>
                    <div style={{ fontSize: "0.92rem", opacity: 0.9 }}>
                      {observerHereNames.length > 0 ? observerHereNames.join(", ") : "No one visible here right now."}
                    </div>
                  </div>
                )}
                <div className="ww-here-chat" style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
                  <div className="ww-chat-messages">
                    {chatMessages.length === 0 && <div className="ww-chat-empty">No one is talking here yet.</div>}
                    {chatMessages.map((m) => (
                      <div key={m.id} className={`ww-chat-msg${m.session_id === sessionId ? " ww-chat-msg--you" : ""}`}>
                        <span className="ww-chat-name">{m.display_name ?? m.session_id.slice(0, 12)}</span>
                        <span className="ww-chat-text">{m.message}</span>
                      </div>
                    ))}
                    <div ref={chatEndRef as RefObject<HTMLDivElement>} />
                  </div>
                  <div className="ww-chat-input-row">
                    <input
                      className="ww-chat-input"
                      type="text"
                      placeholder={observerMode ? "Observer mode is read-only." : "Say aloud… Use @Name to tag someone."}
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") void sendChat(); }}
                      disabled={observerMode || chatPending || !currentViewLocation}
                    />
                    <button
                      className="ww-send-btn"
                      onClick={() => void sendChat()}
                      disabled={observerMode || chatPending || !chatInput.trim() || !currentViewLocation}
                    >
                      {chatPending ? "…" : "→"}
                    </button>
                  </div>
                  {localMentionPreview}
                </div>
              </div>
            )}

            {chatSubTab === "city" && (
              <div className="ww-here-chat" style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
                <div className="ww-chat-messages">
                  {cityMessages.length === 0 && <div className="ww-chat-empty">Nothing said city-wide yet.</div>}
                  {cityMessages.map((m) => (
                    <div key={m.id} className={`ww-chat-msg${m.session_id === sessionId ? " ww-chat-msg--you" : ""}`}>
                      <span className="ww-chat-name">{m.display_name ?? m.session_id.slice(0, 12)}</span>
                      <span className="ww-chat-text">{m.message}</span>
                    </div>
                  ))}
                  <div ref={cityEndRef as RefObject<HTMLDivElement>} />
                </div>
                <div className="ww-chat-input-row">
                  <input
                    className="ww-chat-input"
                    type="text"
                    placeholder={observerMode ? "Observer mode is read-only." : "Broadcast to the city… Use @Name to tag someone."}
                    value={cityInput}
                    onChange={(e) => setCityInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") void sendCityChat(); }}
                    disabled={observerMode || cityPending}
                  />
                  <button className="ww-send-btn" onClick={() => void sendCityChat()} disabled={observerMode || cityPending || !cityInput.trim()}>
                    {cityPending ? "…" : "→"}
                  </button>
                </div>
                {cityMentionPreview}
              </div>
            )}

            {chatSubTab === "global" && (
              <div className="ww-here-chat" style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
                <div className="ww-chat-messages">
                  {globalMessages.length === 0 && <div className="ww-chat-empty">Nothing said globally yet.</div>}
                  {globalMessages.map((m) => (
                    <div key={m.id} className={`ww-chat-msg${m.session_id === sessionId ? " ww-chat-msg--you" : ""}`}>
                      <span className="ww-chat-name">{m.display_name ?? m.session_id.slice(0, 12)}</span>
                      <span className="ww-chat-text">{m.message}</span>
                    </div>
                  ))}
                  <div ref={globalEndRef as RefObject<HTMLDivElement>} />
                </div>
                <div className="ww-chat-input-row">
                  <input
                    className="ww-chat-input"
                    type="text"
                    placeholder={observerMode ? "Observer mode is read-only." : "Broadcast globally… Use @Name to tag someone."}
                    value={globalInput}
                    onChange={(e) => setGlobalInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") void sendGlobalChat(); }}
                    disabled={observerMode || globalPending}
                  />
                  <button className="ww-send-btn" onClick={() => void sendGlobalChat()} disabled={observerMode || globalPending || !globalInput.trim()}>
                    {globalPending ? "…" : "→"}
                  </button>
                </div>
                {globalMentionPreview}
              </div>
            )}

            {chatSubTab === "dms" && (
              <div className="ww-info-inbox-tab">
                <LetterCompose
                  defaultFromName={playerName}
                  sessionId={sessionInboxId}
                  availableRecipients={dmRecipients}
                  preferredRecipient={preferredRecipientKey}
                  onSent={(sent) => {
                    onMessageSent(sent);
                    refreshInbox();
                  }}
                />
                {playerThreads.length > 0 ? (
                  <div className="ww-inbox-list-section" style={{ marginTop: "1rem" }}>
                    <h4 className="ww-info-section-title">Your mail ({playerThreads.length} thread{playerThreads.length === 1 ? "" : "s"})</h4>
                    <div className="ww-thread-layout">
                      <ul className="ww-inbox ww-thread-list">
                        {playerThreads.map((thread) => (
                          <li key={thread.thread_key} className="ww-inbox-letter">
                            <button
                              type="button"
                              className={`ww-thread-list-item${selectedThreadKey === thread.thread_key ? " active" : ""}`}
                              onClick={() => void openPlayerThread(thread)}
                            >
                              <span className="ww-inbox-from">{thread.counterpart}</span>
                              <span className="ww-inbox-thread-meta">
                                {thread.unread_count > 0 ? `${thread.unread_count} unread` : `${thread.messages.length} messages`}
                              </span>
                            </button>
                          </li>
                        ))}
                      </ul>
                      <div className="ww-thread-pane">
                        {playerThreads
                          .filter((thread) => thread.thread_key === selectedThreadKey)
                          .map((thread) => (
                            <div key={thread.thread_key} className="ww-thread-pane-inner">
                              <div className="ww-thread-pane-header">
                                <h5 className="ww-info-section-title">{thread.counterpart}</h5>
                                <span className="ww-inbox-thread-meta">
                                  {thread.last_at ? new Date(thread.last_at).toLocaleString() : ""}
                                </span>
                              </div>
                              <div className="ww-thread">
                                {thread.messages.map((message) => (
                                  <div key={message.dm_id} className={`ww-thread-message ww-thread-message--${message.direction}`}>
                                    <div className="ww-thread-message-meta">
                                      <span>{message.direction === "outbound" ? "You" : thread.counterpart}</span>
                                      {message.sent_at && <span>{new Date(message.sent_at).toLocaleString()}</span>}
                                    </div>
                                    <div className="ww-inbox-body" style={{ marginTop: "0.35rem" }}>
                                      {message.body.replace(/^#[^\n]*\n/, "").trim()}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ))}
                      </div>
                    </div>
                  </div>
                ) : playerInbox.length > 0 ? (
                  <div className="ww-inbox-list-section" style={{ marginTop: "1rem" }}>
                    <h4 className="ww-info-section-title">Your mail ({playerInbox.length})</h4>
                    <ul className="ww-inbox">
                      {playerInbox.map((letter) => (
                        <li key={letter.filename} className="ww-inbox-letter">
                          <details className="ww-inbox-details">
                            <summary className="ww-inbox-summary" style={{ cursor: "pointer", fontWeight: 600 }}>
                              <span className="ww-inbox-from">
                                {letter.filename.replace(/^from_/, "").replace(/_\d{8}-\d{6}\.md$/, "").replace(/_/g, " ")}
                              </span>
                            </summary>
                            <div className="ww-inbox-body" style={{ marginTop: "0.5rem" }}>{letter.body.replace(/^#[^\n]*\n/, "").trim()}</div>
                          </details>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        )}

        <div className="ww-info-map-tab" style={persistentPanelStyle(infoTab === "map")}>
            <div className="ww-map-tab-header">
              <input
                className="ww-map-search"
                type="text"
                placeholder="Search this area for places, tea, parks, vibes…"
                value={mapSearch}
                onChange={(e) => setMapSearch(e.target.value)}
              />
              <div className="ww-map-filter-chips">
                {(["all", "occupied", "quiet", "landmarks"] as const).map((f) => (
                  <button
                    key={f}
                    className={`ww-map-filter-chip${mapFilter === f ? " active" : ""}`}
                    onClick={() => setMapFilter(f)}
                  >
                    {f === "all" ? "All" : f === "occupied" ? "Occupied" : f === "quiet" ? "Quiet" : "Landmarks"}
                  </button>
                ))}
              </div>
            </div>
            <div className="ww-stranded-hint">
              {mapPending
                ? "Updating the graph for this map view…"
                : mapSearch.trim()
                  ? `Showing matches and connected context for “${mapSearch.trim()}”.`
                  : "Pan and zoom the map to refresh what this area can reveal."}
            </div>
            {currentViewLocation && !displayMapNodes.some((n) => n.is_player) && (
              <div className="ww-stranded-hint">
                {observerMode ? (
                  <>
                    You are observing from <strong>{currentViewLocation}</strong>. Click any neighborhood to move your view.
                  </>
                ) : (
                  <>
                    You are at <strong>{currentViewLocation}</strong>. Click any neighborhood to travel there.
                  </>
                )}
              </div>
            )}
            {pendingDest && (
              <div className="ww-move-preview" style={{ marginTop: "0.5rem" }}>
                <span className="ww-move-preview-dest">→ {pendingDest.replace(/_/g, " ")}</span>
                <button className="ww-move-confirm-btn" onClick={confirmRouteMove} disabled={pending}>
                  {observerMode ? "Observe" : "Go"}
                </button>
                <button className="ww-move-cancel-btn" onClick={clearPendingDest}>✕</button>
              </div>
            )}
            <div className="ww-map-tab-body" style={{ flex: 1, position: "relative", marginTop: "0.5rem" }}>
              <LocationMap
                nodes={displayMapNodes}
                edges={mapEdges}
                onNodeClick={!showingEntryScreen && !pending ? handleMapNodeClick : undefined}
                pendingDest={pendingDest}
                pendingPath={pendingPath}
                onViewportChange={setMapViewport}
                searchQuery={mapSearch}
                isVisible={infoTab === "map"}
              />
            </div>
          </div>

        {infoTab === "presence" && (
          <PresencePanel metrics={restMetrics} sessionId={sessionId} onRefresh={() => void refreshRestMetrics()} />
        )}

        {!observerMode && canUseMentorBoard && (
          <div style={persistentPanelStyle(infoTab === "guild")}>
          <GuildBoard
            board={guildBoard}
            pending={guildBoardPending}
            error={guildBoardError}
            onRefresh={() => void refreshGuildBoard()}
            onAssignQuest={assignQuest}
            onIssueStarterPack={issueStarterPacks}
            onResetStarterPack={resetStarterPacks}
            onBootstrapSteward={bootstrapSteward}
            onPatchMemberProfile={patchMemberProfile}
          />
          </div>
        )}

        {infoTab === "guild" && !observerMode && !canUseMentorBoard && (
          <GuildQuestPanel
            displayName={playerName}
            quests={guildQuests}
            pending={guildQuestsPending}
            error={guildQuestsError}
            onRefresh={() => void refreshGuildQuests()}
          />
        )}

        {infoTab === "notes" && (
          <textarea
            className="ww-notes-area"
            placeholder={observerMode ? "Observer mode: notes are disabled in the public viewer." : "Your private notes…"}
            value={playerNotes}
            onChange={(e) => {
              setPlayerNotes(e.target.value);
              localStorage.setItem("ww-player-notes", e.target.value);
            }}
            disabled={observerMode}
          />
        )}
      </div>
    </div>
  );
}
