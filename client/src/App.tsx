import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getWorldDigest,
  getSettingsReadiness,
  getPlayerInbox,
  postLocationChat,
  postMapMove,
  streamAction,
  getAuthMe,
  type WorldDigestResponse,
  type DigestRosterEntry,
  type InboxLetter,
  type LocationChatEntry,
} from "./api/wwClient";
import {
  clearOnboardedSession,
  clearJwt,
  getJwt,
  getOnboardedSessionId,
  getOnboardedWorldId,
  getOrCreateSessionId,
  getPlayerInfo,
  replaceSessionId,
  setJwt,
  setOnboardedSessionId,
  setOnboardedWorldId,
  setPlayerInfo,
  type PlayerInfo,
} from "./state/sessionStore";
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
  const [infoTab, setInfoTab] = useState<"here" | "city" | "groups" | "notes">("here");
  const [playerNotes, setPlayerNotes] = useState<string>(
    () => localStorage.getItem("ww-player-notes") ?? ""
  );
  const [playerInfo, setPlayerInfoState] = useState<PlayerInfo | null>(() => getPlayerInfo());

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
          // Do NOT reset hydratedRef here — that would replace locally-accumulated
          // turn history with the server's third-person event summaries mid-travel.
          // Hydration only needs to run once on initial page load.
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

  // Rehydrate auth state from JWT on mount
  useEffect(() => {
    if (!getJwt()) return;
    getAuthMe()
      .then((me) => {
        setJwt(me.token || getJwt()!);
        const info: PlayerInfo = {
          player_id: me.player_id,
          username: me.username,
          display_name: me.display_name,
          pass_type: me.pass_type,
          pass_expires_at: me.pass_expires_at,
        };
        setPlayerInfo(info);
        setPlayerInfoState(info);
      })
      .catch(() => {
        clearJwt();
        setPlayerInfoState(null);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  async function executeMapMove(destName: string, skipToDestination = false) {
    if (pending) return;
    setPending(true);
    setPendingDest(null);
    try {
      const result = await postMapMove(sessionId, destName, skipToDestination);
      const actionText = result.route_remaining.length > 0
        ? `En route to ${destName.replace(/_/g, " ")} — passing through ${result.to_location.replace(/_/g, " ")}`
        : `Arrive at ${result.to_location.replace(/_/g, " ")}`;
      setTurns((prev) => [
        ...prev,
        {
          id: makeId("turn"),
          ts: new Date().toISOString(),
          action: actionText,
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
    const playerNode = allNodes.find((n) => n.is_player);
    const targetNode = allNodes.find((n) => n.name === nodeName);
    if (!playerNode || !targetNode || playerNode.key === targetNode.key) return;
    // Always stage as pending — user must confirm Go for every destination
    setPendingDest(nodeName);
  }

  function confirmRouteMove() {
    if (pendingDest) {
      setActiveRoute(null);
      setMapOpen(false);
      setDrawerOpen(false);
      void executeMapMove(pendingDest);
    }
  }

  // BFS from player to pendingDest to show the route preview path
  const pendingPath = useMemo<string[]>(() => {
    if (!pendingDest) return [];
    const allNodes = digest?.location_graph?.nodes ?? [];
    const allEdges = digest?.location_graph?.edges ?? [];
    const playerNode = allNodes.find((n) => n.is_player);
    const targetNode = allNodes.find((n) => n.name === pendingDest);
    if (!playerNode || !targetNode) return [];
    // Build adjacency by key (edges are bidirectional)
    const adj = new Map<string, string[]>();
    for (const e of allEdges) {
      if (!adj.has(e.from)) adj.set(e.from, []);
      if (!adj.has(e.to)) adj.set(e.to, []);
      adj.get(e.from)!.push(e.to);
      adj.get(e.to)!.push(e.from);
    }
    const keyToName = new Map(allNodes.map((n) => [n.key, n.name]));
    // BFS for shortest key-path
    const queue: string[][] = [[playerNode.key]];
    const visited = new Set<string>([playerNode.key]);
    while (queue.length > 0) {
      const path = queue.shift()!;
      const current = path[path.length - 1];
      if (current === targetNode.key) {
        return path.map((k) => keyToName.get(k) ?? k);
      }
      for (const neighbor of adj.get(current) ?? []) {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          queue.push([...path, neighbor]);
        }
      }
    }
    return [];
  }, [pendingDest, digest]);

  const [locationSearch, setLocationSearch] = useState<string>("");
  const [mapSearch, setMapSearch] = useState<string>("");
  const [mapFilter, setMapFilter] = useState<"all" | "agents" | "visitors" | "empty">("all");

  const shortSession = sessionId.slice(-10);
  const playerName = digest?.roster.find((r) => r.session_id === sessionId)?.player_name ?? undefined;
  const showingEntryScreen = turns.length === 0 && !draftNarrative && !draftAckLine && getOnboardedSessionId() !== sessionId;
  const nodes = digest?.location_graph?.nodes ?? [];
  const edges = digest?.location_graph?.edges ?? [];

  const _AGENT_SLUG = /^[a-z][a-z0-9_]*[-_]\d{8}/;
  const rosterAgentCount = digest?.roster.filter((r) => _AGENT_SLUG.test(r.session_id)).length ?? 0;
  const rosterHumanCount = (digest?.active_sessions ?? 0) - rosterAgentCount;

  const playerLocation = digest?.roster.find((r) => r.session_id === sessionId)?.location ?? null;
  const hereNode = playerLocation ? nodes.find((n) => n.name === playerLocation) : null;
  const hereAgentCount = hereNode?.agent_count ?? 0;
  const hereHumanCount = playerLocation ? (digest?.location_population?.[playerLocation] ?? 0) : 0;

  const mapNodes = useMemo(() => {
    let result = nodes.filter((n) => n.lat != null && n.lon != null);
    if (mapFilter === "agents") result = result.filter((n) => (n.agent_count ?? 0) > 0);
    else if (mapFilter === "visitors") result = result.filter((n) => n.count > 0);
    else if (mapFilter === "empty") result = result.filter((n) => n.count === 0 && (n.agent_count ?? 0) === 0);
    if (mapSearch.trim()) result = result.filter((n) => n.name.toLowerCase().includes(mapSearch.trim().toLowerCase()));
    return result;
  }, [nodes, mapFilter, mapSearch]);

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
          {digest && (
            <>
              <span className="ww-world-stat" title="People at your location">
                scene: {hereHumanCount + hereAgentCount} here, {hereAgentCount} ai
              </span>
              <span className="ww-world-stat" title="People in the world">
                world: {rosterHumanCount + rosterAgentCount} people, {rosterAgentCount} ai
              </span>
            </>
          )}
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
            className="ww-route-banner-btn ww-route-banner-btn--skip"
            onClick={() => void executeMapMove(activeRoute.destination, true)}
            disabled={pending}
            title="Move directly to destination, dropping traces through intermediate stops"
          >
            {pending ? "…" : "Skip →"}
          </button>
          <button
            className="ww-route-banner-btn"
            onClick={() => void executeMapMove(activeRoute.destination)}
            disabled={pending}
            title="Stop and observe the next location on the way"
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
          {/* ── Top pane: action / narrative (60%) ── */}
          <div className="ww-top-pane">
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
          </div>

          {/* ── Bottom pane: tabbed info / comms (40%) ── */}
          <div className="ww-info-pane">
            <div className="ww-info-tabs">
              {(["here", "city", "groups", "notes"] as const).map((tab) => (
                <button
                  key={tab}
                  className={`ww-info-tab${infoTab === tab ? " ww-info-tab--active" : ""}`}
                  onClick={() => setInfoTab(tab)}
                >
                  {tab === "here"
                    ? (digest?.player_location
                        ? digest.player_location.replace(/_/g, " ")
                        : "Here")
                    : tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>

            <div className="ww-info-body">
              {infoTab === "here" && (
                <>
                  <div className="ww-chat-messages">
                    {chatMessages.length === 0 && (
                      <div className="ww-chat-empty">No one is talking here yet.</div>
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
                      placeholder="Say aloud…"
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") void sendChat(); }}
                      disabled={chatPending || !digest?.player_location}
                    />
                    <button
                      className="ww-send-btn"
                      onClick={() => void sendChat()}
                      disabled={chatPending || !chatInput.trim() || !digest?.player_location}
                    >
                      {chatPending ? "…" : "→"}
                    </button>
                  </div>
                </>
              )}

              {infoTab === "city" && (
                <div className="ww-info-placeholder">
                  <span>City-wide notices — coming soon</span>
                </div>
              )}

              {infoTab === "groups" && (
                <div className="ww-info-placeholder">
                  <span>Groups — coming soon</span>
                </div>
              )}

              {infoTab === "notes" && (
                <textarea
                  className="ww-notes-area"
                  placeholder="Your private notes…"
                  value={playerNotes}
                  onChange={(e) => {
                    setPlayerNotes(e.target.value);
                    localStorage.setItem("ww-player-notes", e.target.value);
                  }}
                />
              )}
            </div>
          </div>
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
                  <button className="ww-move-confirm-btn" onClick={confirmRouteMove} disabled={pending}>Go</button>
                  <button className="ww-move-cancel-btn" onClick={() => setPendingDest(null)}>✕</button>
                </div>
              )}
              <button className="ww-icon-btn" onClick={() => setMapOpen(false)}>✕</button>
            </div>
            <div className="ww-map-filters">
              <input
                className="ww-map-search"
                type="text"
                placeholder="Search locations…"
                value={mapSearch}
                onChange={(e) => setMapSearch(e.target.value)}
              />
              <div className="ww-map-filter-chips">
                {(["all", "agents", "visitors", "empty"] as const).map((f) => (
                  <button
                    key={f}
                    className={`ww-map-filter-chip${mapFilter === f ? " active" : ""}`}
                    onClick={() => setMapFilter(f)}
                  >
                    {f === "all" ? "All" : f === "agents" ? "Agents" : f === "visitors" ? "Visitors" : "Empty"}
                  </button>
                ))}
              </div>
            </div>
            <div className="ww-map-modal-body">
              <LocationMap
                nodes={mapNodes}
                edges={edges}
                onNodeClick={!showingEntryScreen && !pending ? (name) => { handleMapNodeClick(name); } : undefined}
                pendingDest={pendingDest}
                pendingPath={pendingPath}
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
