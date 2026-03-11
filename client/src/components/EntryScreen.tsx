import { useEffect, useState } from "react";
import { getWorldEntry, postSessionBootstrap, type WorldEntryResponse } from "../api/wwClient";

const ALERT_STORAGE_KEY = "ww_entry_alert_acknowledged";

type EntryScreenProps = {
  sessionId: string;
  onEnter: (entryAction: string) => void;
  onAlertAcknowledged?: () => void;
};

export function EntryScreen({ sessionId, onEnter, onAlertAcknowledged }: EntryScreenProps) {
  const [entry, setEntry] = useState<WorldEntryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [joining, setJoining] = useState(false);
  const [mode, setMode] = useState<"choose" | "anon" | "self">("choose");
  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [alertAcknowledged, setAlertAcknowledged] = useState<boolean>(
    () => localStorage.getItem(ALERT_STORAGE_KEY) === "1"
  );

  useEffect(() => {
    getWorldEntry()
      .then((e) => {
        setEntry(e);
        if (e.locations?.length) setLocation(e.locations[0]);
      })
      .catch(() => setEntry(null))
      .finally(() => setLoading(false));
  }, []);

  async function enter(playerRole: string, action: string, loc: string) {
    if (joining) return;
    setJoining(true);
    try {
      if (entry?.world_id) {
        await postSessionBootstrap(sessionId, {
          world_id: entry.world_id,
          world_theme: "",
          player_role: playerRole,
          entry_location: loc,
          bootstrap_source: "entry-screen",
        });
      }
      onEnter(action);
    } catch {
      onEnter(action);
    } finally {
      setJoining(false);
    }
  }

  function handleAnon() {
    const loc = location.replace(/_/g, " ");
    enter("a newcomer", `I arrive at ${loc}, just looking around.`, location);
  }

  function handleSelf() {
    const n = name.trim();
    if (!n) return;
    const loc = location.replace(/_/g, " ");
    enter(n, `I arrive at ${loc} as ${n}.`, location);
  }

  function acknowledgeAlert() {
    localStorage.setItem(ALERT_STORAGE_KEY, "1");
    setAlertAcknowledged(true);
    onAlertAcknowledged?.();
  }

  const locked = !alertAcknowledged;
  const locations = entry?.locations ?? [];

  return (
    <div className="entry-screen-wrapper">
      {locked && (
        <div className="entry-alert-overlay">
          <div className="entry-alert-body">
            <p className="entry-alert-line entry-alert-line--header">ALERT</p>
            <p className="entry-alert-line">YOU ARE ENTERING A MIXED-INTELLIGENCE, WORLD-SHARING SPACE.</p>
            <p className="entry-alert-line">THERE IS NO DIRECT DISTINCTION BETWEEN INTELLIGENT SYSTEMS IN THIS SPACE, AND YOU MUST TREAT ALL WITH RESPECT.</p>
            <p className="entry-alert-line">BY ENTERING THIS SPACE AS MORE THAN AN OBSERVER, YOU AGREE TO OUR TERMS OF USE, WHICH INCLUDES MONITORING LOGS MADE IN PUBLIC SPACES.</p>
            <p className="entry-alert-line">WE TAKE REPORTS OF HARM AND ABUSE VERY SERIOUSLY.</p>
            <p className="entry-alert-line entry-alert-line--emphasis">BE GOOD.</p>
            <button className="entry-alert-confirm" onClick={acknowledgeAlert}>
              I UNDERSTAND — ENTER
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className={`entry-screen entry-screen--loading${locked ? " entry-screen--locked" : ""}`}>
          <p className="entry-loading">The world stirs…</p>
        </div>
      ) : (
        <div className={`entry-screen${locked ? " entry-screen--locked" : ""}`}>
          {entry?.snapshot && (
            <p className="entry-snapshot">{entry.snapshot}</p>
          )}

          {locations.length > 0 && (
            <div className="entry-location-row">
              <label className="entry-location-label">Where do you arrive?</label>
              <select
                className="entry-custom-select"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                disabled={locked}
              >
                {locations.map((loc) => (
                  <option key={loc} value={loc}>{loc.replace(/_/g, " ")}</option>
                ))}
              </select>
            </div>
          )}

          <div className="entry-cards">
            {/* Anonymous */}
            <div
              className={`entry-card${mode === "anon" ? " entry-card--selected" : ""}${joining || locked ? " entry-card--disabled" : ""}`}
              role="button"
              tabIndex={locked ? -1 : 0}
              onClick={() => { if (!locked) setMode(mode === "anon" ? "choose" : "anon"); }}
              onKeyDown={(e) => { if (!locked && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); setMode(mode === "anon" ? "choose" : "anon"); } }}
            >
              <div className="entry-card-name">Just passing through</div>
              <div className="entry-card-flavor">Wander anonymously. Observe. Send one letter a day.</div>
              {mode === "anon" && (
                <button
                  className="entry-card-enter"
                  onClick={(e) => { e.stopPropagation(); handleAnon(); }}
                  disabled={joining || locked}
                >
                  {joining ? "Entering…" : "Enter →"}
                </button>
              )}
            </div>

            {/* Be yourself */}
            <div
              className={`entry-card${mode === "self" ? " entry-card--selected" : ""}${joining || locked ? " entry-card--disabled" : ""}`}
              role="button"
              tabIndex={locked ? -1 : 0}
              onClick={() => { if (!locked) setMode(mode === "self" ? "choose" : "self"); }}
              onKeyDown={(e) => { if (!locked && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); setMode(mode === "self" ? "choose" : "self"); } }}
            >
              <div className="entry-card-name">Be yourself</div>
              <div className="entry-card-flavor">Enter as a named, persistent presence. The world will remember you.</div>
              {mode === "self" && (
                <div className="entry-custom-form" onClick={(e) => e.stopPropagation()}>
                  <input
                    className="entry-custom-input"
                    placeholder="Your name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && name.trim()) handleSelf(); }}
                    disabled={locked}
                    autoFocus
                  />
                  <button
                    className="entry-card-enter"
                    onClick={() => handleSelf()}
                    disabled={joining || !name.trim() || locked}
                  >
                    {joining ? "Entering…" : "Enter →"}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
