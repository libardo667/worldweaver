import { useCallback, useEffect, useRef, useState } from "react";

import {
  getWorldDigest,
  getSettingsReadiness,
  streamAction,
  type WorldDigestResponse,
  type DigestRosterEntry,
  type DigestTimelineEntry,
} from "./api/wwClient";
import { getOrCreateSessionId, replaceSessionId } from "./state/sessionStore";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { SetupModal } from "./components/SetupModal";
import { ErrorToastStack } from "./components/ErrorToastStack";
import { ConstellationView } from "./views/ConstellationView";
import { EntryScreen } from "./components/EntryScreen";
import { LetterCompose } from "./components/LetterCompose";
import type { SettingsReadinessResponse, ToastItem } from "./types";

function makeId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

type Turn = {
  id: string;
  action: string;
  ackLine: string | null;
  narrative: string;
  location: string | null;
};

const MIN_DIGEST_WIDTH = 200;
const MAX_DIGEST_WIDTH = 600;
const DEFAULT_DIGEST_WIDTH = 300;

export default function App() {
  const [tab, setTab] = useState<"play" | "constellation">("play");
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
  const [digestWidth, setDigestWidth] = useState(DEFAULT_DIGEST_WIDTH);

  const narrativeEndRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null);

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
      const d = await getWorldDigest(20);
      setDigest(d);
    } catch {
      // silent — digest is best-effort
    }
  }, []);

  useEffect(() => {
    void refreshReadiness();
    void refreshDigest();
  }, [refreshReadiness, refreshDigest]);

  useEffect(() => {
    const interval = window.setInterval(() => void refreshDigest(), 30_000);
    return () => window.clearInterval(interval);
  }, [refreshDigest]);

  useEffect(() => {
    narrativeEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, draftNarrative, draftAckLine]);

  // ── Resize handle drag ────────────────────────────────────────────────────
  function handleResizeMouseDown(e: React.MouseEvent) {
    e.preventDefault();
    dragRef.current = { startX: e.clientX, startWidth: digestWidth };

    function onMouseMove(ev: MouseEvent) {
      if (!dragRef.current) return;
      const delta = dragRef.current.startX - ev.clientX;
      const next = Math.min(MAX_DIGEST_WIDTH, Math.max(MIN_DIGEST_WIDTH, dragRef.current.startWidth + delta));
      setDigestWidth(next);
    }
    function onMouseUp() {
      dragRef.current = null;
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    }
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }

  // ── Action submit ─────────────────────────────────────────────────────────
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
          action: text.trim(),
          ackLine: result.ack_line || capturedAck || null,
          narrative: result.narrative,
          location: (result.state_changes?.location as string) ?? null,
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
    abortRef.current?.abort();
    const next = replaceSessionId();
    setSessionId(next);
    setTurns([]);
    setDraftAckLine("");
    setDraftNarrative("");
    setActionText("");
  }

  async function handleConstellationJump(location: string) {
    setTab("play");
    void submitAction(`I go to ${location}.`);
  }

  const shortSession = sessionId.slice(-10);

  // Player display name from most recent bootstrap event visible in digest
  const playerName = digest?.roster.find((r) => r.session_id === sessionId)?.player_name ?? undefined;

  return (
    <div className="ww-shell">
      <header className="ww-topbar">
        <span className="ww-topbar-title">WorldWeaver</span>
        <nav className="ww-tabs">
          <button
            className={`ww-tab${tab === "play" ? " active" : ""}`}
            onClick={() => setTab("play")}
          >
            Play
          </button>
          <button
            className={`ww-tab${tab === "constellation" ? " active" : ""}`}
            onClick={() => setTab("constellation")}
          >
            Constellation
          </button>
        </nav>
        <div className="ww-topbar-right">
          <span className="ww-session-label" title={sessionId}>
            …{shortSession}
          </span>
          <button className="ww-icon-btn" onClick={handleNewSession} title="New session">↺</button>
          <button className="ww-icon-btn" onClick={() => setIsSettingsOpen(true)} title="Settings">⚙</button>
        </div>
      </header>

      {tab === "constellation" ? (
        <ConstellationView sessionId={sessionId} onJumpToLocation={handleConstellationJump} />
      ) : (
        <div className="ww-play">
          <div className="ww-narrative-col">
            <div className="ww-narrative-scroll">
              {turns.length === 0 && !draftNarrative && !draftAckLine && (
                <EntryScreen
                  sessionId={sessionId}
                  onEnter={(action) => {
                    void submitAction(action);
                  }}
                />
              )}
              {turns.map((turn) => (
                <div key={turn.id} className="ww-turn">
                  <div className="ww-turn-action">&gt; {turn.action}</div>
                  {turn.ackLine && (
                    <div className="ww-turn-ack">{turn.ackLine}</div>
                  )}
                  <div className="ww-turn-narrative">{turn.narrative}</div>
                  {turn.location && (
                    <div className="ww-turn-location">
                      {turn.location.replace(/_/g, " ")}
                    </div>
                  )}
                </div>
              ))}
              {(draftAckLine || draftNarrative || pending) && (
                <div className="ww-turn ww-turn--draft">
                  {draftAckLine && (
                    <div className="ww-turn-ack">{draftAckLine}</div>
                  )}
                  {draftNarrative
                    ? <div>{draftNarrative}</div>
                    : !draftAckLine && <span className="ww-typing">…</span>}
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
                disabled={pending}
                autoFocus
              />
              <button
                className="ww-send-btn"
                onClick={() => { const t = actionText; setActionText(""); void submitAction(t); }}
                disabled={pending || !actionText.trim()}
              >
                {pending ? "…" : "→"}
              </button>
            </div>
          </div>

          {/* Resize handle */}
          <div
            className="ww-resize-handle"
            onMouseDown={handleResizeMouseDown}
            title="Drag to resize"
          />

          <aside className="ww-digest-col" style={{ width: digestWidth, minWidth: digestWidth }}>
            <div className="ww-digest-header">
              <span>World</span>
              <button className="ww-text-btn" onClick={() => void refreshDigest()}>↺</button>
            </div>

            {digest ? (
              <>
                <section className="ww-digest-section">
                  <LetterCompose defaultFromName={playerName} />
                </section>

                {!digest.seeded && (
                  <p className="ww-digest-empty">No world seeded.</p>
                )}

                {digest.roster.length > 0 && (
                  <section className="ww-digest-section">
                    <h4 className="ww-digest-section-title">
                      Inhabitants ({digest.active_sessions})
                    </h4>
                    <ul className="ww-roster">
                      {digest.roster.map((r: DigestRosterEntry) => (
                        <li
                          key={r.session_id}
                          className={`ww-roster-entry${r.session_id === sessionId ? " ww-roster-entry--you" : ""}`}
                        >
                          <span className="ww-roster-name">
                            {r.player_name ?? (r.session_id === sessionId ? "you" : r.session_id.slice(0, 8))}
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

                {Object.keys(digest.location_population).length > 0 && (
                  <section className="ww-digest-section">
                    <h4 className="ww-digest-section-title">Locations</h4>
                    <ul className="ww-locations">
                      {Object.entries(digest.location_population).map(([loc, count]) => (
                        <li key={loc} className="ww-location-entry">
                          <span>{loc.replace(/_/g, " ")}</span>
                          <span className="ww-location-count">{count}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}

                {digest.timeline.length > 0 && (
                  <section className="ww-digest-section">
                    <h4 className="ww-digest-section-title">Recent events</h4>
                    <ul className="ww-timeline">
                      {digest.timeline.map((e: DigestTimelineEntry, i: number) => (
                        <li key={i} className="ww-timeline-entry">
                          <span className="ww-timeline-who">
                            {e.who ? e.who.slice(0, 12) : "?"}
                          </span>
                          <span className="ww-timeline-summary">{e.summary}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}

              </>
            ) : (
              <p className="ww-digest-empty">Loading…</p>
            )}
          </aside>
        </div>
      )}

      <ErrorToastStack toasts={toasts} onDismiss={dismissToast} />

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
