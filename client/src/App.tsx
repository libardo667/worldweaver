import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getWorldDigest,
  getSettingsReadiness,
  getPlayerInbox,
  postLocationChat,
  postMapMove,
  streamAction,
  type WorldDigestResponse,
  type DigestRosterEntry,
  type InboxLetter,
  type LocationChatEntry,
} from "./api/wwClient";
import { clearOnboardedSession, getOnboardedSessionId, getOnboardedWorldId, getOrCreateSessionId, replaceSessionId, setOnboardedSessionId, setOnboardedWorldId } from "./state/sessionStore";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { SetupModal } from "./components/SetupModal";
import { ErrorToastStack } from "./components/ErrorToastStack";
import { EntryScreen } from "./components/EntryScreen";
import { LetterCompose } from "./components/LetterCompose";
import { LocationMap } from "./components/LocationMap";
import type { SettingsReadinessResponse, ToastItem } from "./types";

function makeId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

type Turn = {
  id: string;
  ts: string;
  action: string;
  ackLine: string | null;
  narrative: string;
  location: string | null;
};

export default function App() {
  const [sessionId, setSessionId] = useState<string>(() => getOrCreateSessionId());
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draftAckLine, setDraftAckLine] = useState<string>("");
  const [draftNarrative, setDraftNarrative] = useState<string>("");
  const [actionText, setActionText] = useState<string>("");
  const [pending, setPending] = useState(false);
  const [digest, setDigest] = useState<WorldDigestResponse | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settingsReadiness, setSettingsReadiness] = useState<SettingsReadinessResponse | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [mapOpen, setMapOpen] = useState(false);
  const [playerInbox, setPlayerInbox] = useState<InboxLetter[]>([]);
  const [agentFeed, setAgentFeed] = useState<Array<{ ts: string; displayName: string; agentAction: string | null; narrative: string | null }>>([]);
  const [chatMessages, setChatMessages] = useState<LocationChatEntry[]>([]);
  const [chatInput, setChatInput] = useState<string>("");
  const [chatPending, setChatPending] = useState(false);

  const narrativeEndRef = useRef<HTMLDivElement | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const seenAgentTsRef = useRef<Set<string>>(new Set());
  const seenChatIdsRef = useRef<Set<number>>(new Set());
  const hydratedRef = useRef(false);
  const playerLocationRef = useRef<string | null>(null);

  const pushToast = useCallback(
    (title: string, detail?: string, kind: ToastItem["kind"] = "error") => {
      const toast: ToastItem = { id: makeId("toast"), title, detail, kind };
      setToasts((prev) => [toast, ...prev].slice(0, 4));
    },
    [],
  );

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const refreshReadiness = useCallback(async () => {
    try {
      const r = await getSettingsReadiness();
      setSettingsReadiness(r);
    } catch {
      // silent
    }
  }, []);

  const refreshDigest = useCallback(async () => {
    try {
      const d = await getWorldDigest(sessionId, 20);
      setDigest(d);

      if (d.world_id && d.world_id !== getOnboardedWorldId()) {
        clearOnboardedSession();
      }

      const SUMMARY_RE = /^Player action:\s*([\s\S]*?)\s*Result:\s*([\s\S]*)$/;

      if (d.timeline && d.player_location) {
        // When the player moves to a new location, reset the agent feed so
        // events from previous locations don't bleed into the current view.
        if (d.player_location !== playerLocationRef.current) {
          playerLocationRef.current = d.player_location;
          seenAgentTsRef.current = new Set();
          seenChatIdsRef.current = new Set();
          setAgentFeed([]);
          setChatMessages([]);
          hydratedRef.current = false;
        }

        if (!hydratedRef.current) {
          hydratedRef.current = true;
          const playerEvents = d.timeline
            .filter((e) => e.who === sessionId && e.summary && e.ts)
            .sort((a, b) => (a.ts ?? "").localeCompare(b.ts ?? ""));
          if (playerEvents.length > 0) {
            const hydratedTurns: Turn[] = playerEvents.map((e) => {
              const match = e.summary ? SUMMARY_RE.exec(e.summary) : null;
              return {
                id: makeId("turn"),
                ts: e.ts!,
                action: match ? match[1] : (e.summary ?? ""),
                ackLine: null,
                narrative: match ? match[2] : (e.summary ?? ""),
                location: e.destination ?? e.location ?? null,
              };
            });
            setTurns(hydratedTurns);
          }
          const agentEvents = d.timeline
            .filter((e) => e.who !== sessionId && e.summary && e.ts)
            .map((e) => {
              const match = e.summary ? SUMMARY_RE.exec(e.summary) : null;
              return {
                ts: e.ts!,
                displayName: e.display_name ?? (e.who ? e.who.slice(0, 12) : "?"),
                agentAction: match ? match[1] : null,
                narrative: match ? match[2] : (e.summary ?? null),
              };
            });
          agentEvents.forEach((item) => seenAgentTsRef.current.add(item.ts));
          if (agentEvents.length > 0) setAgentFeed(agentEvents.slice(-20));
        }

        const newItems = d.timeline
          .filter((e) => e.who !== sessionId && e.summary && e.ts && !seenAgentTsRef.current.has(e.ts))
          .map((e) => {
            const match = e.summary ? SUMMARY_RE.exec(e.summary) : null;
            return {
              ts: e.ts!,
              displayName: e.display_name ?? (e.who ? e.who.slice(0, 12) : "?"),
              agentAction: match ? match[1] : null,
              narrative: match ? match[2] : (e.summary ?? null),
            };
          });
        if (newItems.length > 0) {
          newItems.forEach((item) => seenAgentTsRef.current.add(item.ts));
          setAgentFeed((prev) => [...prev, ...newItems].slice(-20));
        }

        // Chat messages come from the digest directly
        if (d.location_chat) {
          const newChat = d.location_chat.filter((m) => !seenChatIdsRef.current.has(m.id));
          if (newChat.length > 0) {
            newChat.forEach((m) => seenChatIdsRef.current.add(m.id));
            setChatMessages((prev) => [...prev, ...newChat].slice(-50));
          }
        }
      }
    } catch {
      // silent
    }
  }, [sessionId]);

  const refreshInbox = useCallback(async (sid: string) => {
    try {
      const r = await getPlayerInbox(sid);
      setPlayerInbox(r.letters);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    void refreshReadiness();
    void refreshDigest();
    void refreshInbox(sessionId);
  }, [refreshReadiness, refreshDigest, refreshInbox, sessionId]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void refreshDigest();
      void refreshInbox(sessionId);
    }, 30_000);
    return () => window.clearInterval(interval);
  }, [refreshDigest, refreshInbox, sessionId]);

  useEffect(() => {
    narrativeEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, draftNarrative, agentFeed]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  async function sendChat() {
    const msg = chatInput.trim();
    if (!msg || chatPending || !digest?.player_location) return;
    setChatPending(true);
    setChatInput("");
    const displayName = digest.roster.find((r) => r.session_id === sessionId)?.player_name ?? undefined;
    try {
      const result = await postLocationChat(digest.player_location, sessionId, msg, displayName);
      const optimistic: LocationChatEntry = {
        id: result.id,
        session_id: sessionId,
        display_name: displayName ?? null,
        message: msg,
        ts: result.ts,
      };
      seenChatIdsRef.current.add(result.id);
      setChatMessages((prev) => [...prev, optimistic].slice(-50));
    } catch {
      // silent — message will reappear on next digest poll
    } finally {
      setChatPending(false);
    }
  }

  async function submitAction(text: string) {
    if (!text.trim() || pending) return;

    setPending(true);
    setDraftAckLine("");
    setDraftNarrative("");

    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    let capturedAck = "";

    try {
      const result = await streamAction(
        sessionId,
        text.trim(),
        undefined,
        (chunk) => setDraftNarrative((prev) => prev + chunk),
        ctrl.signal,
        (ack) => { capturedAck = ack; setDraftAckLine(ack); },
      );
      setTurns((prev) => [
        ...prev,
        {
          id: makeId("turn"),
          ts: new Date().toISOString(),
          action: text.trim(),
          ackLine: result.ack_line || capturedAck || null,
          narrative: result.narrative,
          location: (result.state_changes?.destination as string) ?? (result.state_changes?.location as string) ?? null,
        },
      ]);
      setDraftAckLine("");
      setDraftNarrative("");
      void refreshDigest();
    } catch (err: unknown) {
      if ((err as { name?: string })?.name !== "AbortError") {
        pushToast("Action failed.", String(err));
      }
    } finally {
      setPending(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const text = actionText;
      setActionText("");
      void submitAction(text);
    }
  }

  function handleNewSession() {
    if (!window.confirm("Start a new session? You'll enter the world as a stranger — your current character will be left behind.")) return;
    abortRef.current?.abort();
    const next = replaceSessionId();
    setSessionId(next);
    setTurns([]);
    setDraftAckLine("");
    setDraftNarrative("");
    setActionText("");
    setAgentFeed([]);
    seenAgentTsRef.current = new Set();
    hydratedRef.current = false;
  }

  const [pendingDest, setPendingDest] = useState<string | null>(null);
  const [activeRoute, setActiveRoute] = useState<{ destination: string; remaining: string[] } | null>(null);

  async function executeMapMove(destName: string) {
    if (pending) return;
    setPending(true);
    setPendingDest(null);
    try {
      const result = await postMapMove(sessionId, destName);
      setTurns((prev) => [
        ...prev,
        {
          id: makeId("turn"),
          ts: new Date().toISOString(),
          action: result.route_remaining.length > 0
            ? `En route to ${destName.replace(/_/g, " ")} — passing through ${result.to_location.replace(/_/g, " ")}`
            : `Arrive at ${result.to_location.replace(/_/g, " ")}`,
          ackLine: null,
          narrative: result.narrative,
          location: result.to_location,
        },
      ]);
      if (result.route_remaining.length > 0) {
        setActiveRoute({ destination: destName, remaining: result.route_remaining });
      } else {
        setActiveRoute(null);
      }
      void refreshDigest();
    } catch (err) {
      pushToast("Move failed.", String(err));
      setActiveRoute(null);
    } finally {
      setPending(false);
    }
  }

  function handleMapNodeClick(nodeName: string) {
    const allNodes = digest?.location_graph?.nodes ?? [];
    const edges = digest?.location_graph?.edges ?? [];
    const playerNode = allNodes.find((n) => n.is_player);
    const targetNode = allNodes.find((n) => n.name === nodeName);
    if (!playerNode || !targetNode || playerNode.key === targetNode.key) return;
    // If clicking the current active route destination, continue the journey
    if (activeRoute && nodeName === activeRoute.destination) {
      void executeMapMove(nodeName);
      return;
    }
    // New destination — set route or move directly if adjacent
    const isAdjacent = edges.some(
      (e) =>
        (e.from === playerNode.key && e.to === targetNode.key) ||
        (e.to === playerNode.key && e.from === targetNode.key),
    );
    if (isAdjacent) {
      setActiveRoute(null);
      void executeMapMove(nodeName);
    } else {
      setPendingDest(nodeName);
    }
  }

  function confirmRouteMove() {
    if (pendingDest) {
      setActiveRoute(null);
      void executeMapMove(pendingDest);
    }
  }

  const [locationSearch, setLocationSearch] = useState<string>("");

  const shortSession = sessionId.slice(-10);
  const playerName = digest?.roster.find((r) => r.session_id === sessionId)?.player_name ?? undefined;
  const showingEntryScreen = turns.length === 0 && !draftNarrative && !draftAckLine && getOnboardedSessionId() !== sessionId;
  const nodes = digest?.location_graph?.nodes ?? [];
  const edges = digest?.location_graph?.edges ?? [];

  // One-hop reachable nodes from the player's current location (edges are bidirectional)
  const oneHopKeys = useMemo(() => {
    const playerNode = nodes.find((n) => n.is_player);
    if (!playerNode) return null;
    const reachable = new Set<string>([playerNode.key]);
    for (const e of edges) {
      if (e.from === playerNode.key) reachable.add(e.to);
      else if (e.to === playerNode.key) reachable.add(e.from);
    }
    return reachable;
  }, [nodes, edges]);

  const filteredNodes = locationSearch.trim()
    ? nodes.filter((n) => n.name.toLowerCase().includes(locationSearch.trim().toLowerCase()))
    : oneHopKeys
      ? nodes.filter((n) => oneHopKeys.has(n.key))
      : nodes;

  return (
    <div className="ww-shell">
      <header className="ww-topbar">
        <span className="ww-topbar-title">WorldWeaver</span>
        <div className="ww-topbar-right">
          <span className="ww-session-label" title={sessionId}>…{shortSession}</span>
          <button className="ww-icon-btn" onClick={handleNewSession} title="New session">↺</button>
          <button className="ww-icon-btn" onClick={() => setIsSettingsOpen(true)} title="Settings">⚙</button>
          <button
            className={`ww-icon-btn${drawerOpen ? " active" : ""}`}
            onClick={() => setDrawerOpen((o) => !o)}
            title="World"
          >☰</button>
        </div>
      </header>

      {activeRoute && (
        <div className="ww-route-banner">
          <span className="ww-route-banner-label">
            → {activeRoute.destination.replace(/_/g, " ")}
            <span className="ww-route-banner-hops"> · {activeRoute.remaining.length} stop{activeRoute.remaining.length !== 1 ? "s" : ""}</span>
          </span>
          <button
            className="ww-route-banner-btn"
            onClick={() => void executeMapMove(activeRoute.destination)}
            disabled={pending}
          >
            {pending ? "…" : "Next hop →"}
          </button>
          <button
            className="ww-route-banner-cancel"
            onClick={() => setActiveRoute(null)}
            title="Cancel route"
          >✕</button>
        </div>
      )}

      <div className="ww-body">
        <div className="ww-narrative-col">
          <div className="ww-narrative-scroll">
            {turns.length === 0 && !draftNarrative && !draftAckLine && getOnboardedSessionId() !== sessionId && (
              <EntryScreen
                sessionId={sessionId}
                onEnter={(action) => {
                  setOnboardedSessionId(sessionId);
                  if (digest?.world_id) setOnboardedWorldId(digest.world_id);
                  void submitAction(action);
                }}
              />
            )}
            {[
              ...turns.map((t) => ({ kind: "turn" as const, ts: t.ts, data: t })),
              ...agentFeed.map((a) => ({ kind: "agent" as const, ts: a.ts, data: a })),
            ]
              .sort((a, b) => a.ts.localeCompare(b.ts))
              .map((item) =>
                item.kind === "turn" ? (
                  <div key={item.data.id} className="ww-turn">
                    <div className="ww-turn-action">&gt; {item.data.action}</div>
                    {item.data.ackLine && (
                      <div className="ww-turn-ack">{item.data.ackLine}</div>
                    )}
                    <div className="ww-turn-narrative">{item.data.narrative}</div>
                    {item.data.location && (
                      <div className="ww-turn-location">
                        {item.data.location.replace(/_/g, " ")}
                      </div>
                    )}
                  </div>
                ) : (
                  <div key={item.data.ts} className="ww-turn ww-turn--agent">
                    <div className="ww-turn-agent-name">{item.data.displayName}</div>
                    <div className="ww-turn-narrative">{item.data.narrative ?? item.data.agentAction}</div>
                  </div>
                )
              )}
            {(draftNarrative || pending) && (
              <div className="ww-turn ww-turn--draft">
                {draftNarrative
                  ? <div>{draftNarrative}</div>
                  : <span className="ww-typing">…</span>}
              </div>
            )}
            <div ref={narrativeEndRef} />
          </div>

          <div className="ww-input-row">
            <textarea
              className="ww-action-input"
              placeholder="What do you do?"
              rows={2}
              value={actionText}
              onChange={(e) => setActionText(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={pending || showingEntryScreen}
              autoFocus
            />
            <button
              className="ww-send-btn"
              onClick={() => { const t = actionText; setActionText(""); void submitAction(t); }}
              disabled={pending || showingEntryScreen || !actionText.trim()}
            >
              {pending ? "…" : "→"}
            </button>
          </div>

          {digest?.player_location && (
            <div className="ww-chat-pane">
              <div className="ww-chat-header">
                Chat — {digest.player_location.replace(/_/g, " ")}
              </div>
              <div className="ww-chat-messages">
                {chatMessages.length === 0 && (
                  <div className="ww-chat-empty">No messages here yet.</div>
                )}
                {chatMessages.map((m) => (
                  <div
                    key={m.id}
                    className={`ww-chat-msg${m.session_id === sessionId ? " ww-chat-msg--you" : ""}`}
                  >
                    <span className="ww-chat-name">{m.display_name ?? m.session_id.slice(0, 12)}</span>
                    <span className="ww-chat-text">{m.message}</span>
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>
              <div className="ww-chat-input-row">
                <input
                  className="ww-chat-input"
                  type="text"
                  placeholder="Say something…"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") void sendChat(); }}
                  disabled={chatPending}
                />
                <button
                  className="ww-send-btn"
                  onClick={() => void sendChat()}
                  disabled={chatPending || !chatInput.trim()}
                >
                  {chatPending ? "…" : "→"}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* World drawer */}
        {drawerOpen && (
          <div className="ww-drawer-backdrop" onClick={() => setDrawerOpen(false)} />
        )}
        <aside className={`ww-drawer${drawerOpen ? " open" : ""}`}>
          <div className="ww-drawer-header">
            <span>World</span>
            <button className="ww-icon-btn" onClick={() => setDrawerOpen(false)}>✕</button>
          </div>

          {digest ? (
            <>
              {nodes.length > 0 && (
                <section className="ww-drawer-section">
                  <div className="ww-drawer-section-header">
                    <h4 className="ww-drawer-section-title">Locations</h4>
                    <button
                      className="ww-map-open-btn"
                      onClick={() => setMapOpen(true)}
                      title="Open map"
                    >
                      Map
                    </button>
                  </div>
                  {pendingDest && (
                    <div className="ww-move-preview">
                      <span className="ww-move-preview-dest">→ {pendingDest.replace(/_/g, " ")}</span>
                      <button
                        className="ww-move-confirm-btn"
                        onClick={confirmRouteMove}
                        disabled={pending}
                      >
                        Go
                      </button>
                      <button
                        className="ww-move-cancel-btn"
                        onClick={() => setPendingDest(null)}
                      >
                        ✕
                      </button>
                    </div>
                  )}
                  <input
                    className="ww-location-search"
                    type="text"
                    placeholder="Search…"
                    value={locationSearch}
                    onChange={(e) => setLocationSearch(e.target.value)}
                  />
                  <ul className="ww-location-list">
                    {filteredNodes.map((node) => (
                      <li
                        key={node.key}
                        className={`ww-location-item${node.is_player ? " ww-location-item--here" : ""}${pendingDest === node.name ? " ww-location-item--pending" : ""}`}
                        onClick={() => !showingEntryScreen && !pending && handleMapNodeClick(node.name)}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => { if (e.key === "Enter" && !showingEntryScreen && !pending) handleMapNodeClick(node.name); }}
                      >
                        <span className="ww-location-name">{node.name.replace(/_/g, " ")}</span>
                        {node.count > 0 && (
                          <span className="ww-location-count">{node.count}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {digest.roster.length > 0 && (
                <section className="ww-drawer-section">
                  <h4 className="ww-drawer-section-title">
                    Inhabitants ({digest.active_sessions})
                  </h4>
                  <ul className="ww-roster">
                    {digest.roster.map((r: DigestRosterEntry) => (
                      <li
                        key={r.session_id}
                        className={`ww-roster-entry${r.session_id === sessionId ? " ww-roster-entry--you" : ""}`}
                      >
                        <span className="ww-roster-name">
                          {r.display_name ?? r.session_id.slice(0, 12)}
                          {r.session_id === sessionId && <span className="ww-roster-you"> (you)</span>}
                        </span>
                        <span className="ww-roster-loc">
                          {r.location !== "unknown" ? r.location.replace(/_/g, " ") : "—"}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <section className="ww-drawer-section">
                <LetterCompose defaultFromName={playerName} sessionId={sessionId} availableAgents={digest.known_agents} />
              </section>

              {playerInbox.length > 0 && (
                <section className="ww-drawer-section">
                  <h4 className="ww-drawer-section-title">Your mail ({playerInbox.length})</h4>
                  <ul className="ww-inbox">
                    {playerInbox.map((letter) => (
                      <li key={letter.filename} className="ww-inbox-letter">
                        <div className="ww-inbox-from">
                          {letter.filename.replace(/^from_/, "").replace(/_\d{8}-\d{6}\.md$/, "").replace(/_/g, " ")}
                        </div>
                        <div className="ww-inbox-body">{letter.body.replace(/^#[^\n]*\n/, "").trim()}</div>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          ) : (
            <p className="ww-drawer-empty">Loading…</p>
          )}
        </aside>
      </div>

      <ErrorToastStack toasts={toasts} onDismiss={dismissToast} />

      {/* Map modal */}
      {mapOpen && (
        <>
          <div className="ww-map-modal-backdrop" onClick={() => setMapOpen(false)} />
          <div className="ww-map-modal">
            <div className="ww-map-modal-header">
              <span className="ww-map-modal-title">Map</span>
              {pendingDest && (
                <div className="ww-move-preview ww-move-preview--inline">
                  <span className="ww-move-preview-dest">→ {pendingDest.replace(/_/g, " ")}</span>
                  <button className="ww-move-confirm-btn" onClick={() => { confirmRouteMove(); setMapOpen(false); }} disabled={pending}>Go</button>
                  <button className="ww-move-cancel-btn" onClick={() => setPendingDest(null)}>✕</button>
                </div>
              )}
              <button className="ww-icon-btn" onClick={() => setMapOpen(false)}>✕</button>
            </div>
            <div className="ww-map-modal-body">
              <LocationMap
                nodes={digest?.location_graph?.nodes ?? []}
                edges={digest?.location_graph?.edges ?? []}
                onNodeClick={!showingEntryScreen && !pending ? (name) => { handleMapNodeClick(name); } : undefined}
                pendingDest={pendingDest}
              />
            </div>
          </div>
        </>
      )}

      <SettingsDrawer
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onModelChanged={() => void refreshReadiness()}
      />

      {settingsReadiness && !settingsReadiness.ready && (
        <SetupModal
          missing={settingsReadiness.missing}
          onComplete={() => void refreshReadiness()}
        />
      )}
    </div>
  );
}
