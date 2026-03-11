import { useEffect, useState } from "react";
import { getWorldEntry, postSessionBootstrap, type WorldEntryResponse } from "../api/wwClient";

type EntryScreenProps = {
  sessionId: string;
  onEnter: (entryAction: string) => void;
};

export function EntryScreen({ sessionId, onEnter }: EntryScreenProps) {
  const [entry, setEntry] = useState<WorldEntryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [joining, setJoining] = useState(false);
  const [mode, setMode] = useState<"choose" | "anon" | "self">("choose");
  const [name, setName] = useState("");
  const [location, setLocation] = useState("");

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

  const locations = entry?.locations ?? [];

  if (loading) {
    return (
      <div className="entry-screen entry-screen--loading">
        <p className="entry-loading">The world stirs…</p>
      </div>
    );
  }

  return (
    <div className="entry-screen">
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
          className={`entry-card${mode === "anon" ? " entry-card--selected" : ""}${joining ? " entry-card--disabled" : ""}`}
          role="button"
          tabIndex={0}
          onClick={() => setMode(mode === "anon" ? "choose" : "anon")}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setMode(mode === "anon" ? "choose" : "anon"); } }}
        >
          <div className="entry-card-name">Just passing through</div>
          <div className="entry-card-flavor">Wander anonymously. Observe. Send one letter a day.</div>
          {mode === "anon" && (
            <button
              className="entry-card-enter"
              onClick={(e) => { e.stopPropagation(); handleAnon(); }}
              disabled={joining}
            >
              {joining ? "Entering…" : "Enter →"}
            </button>
          )}
        </div>

        {/* Be yourself */}
        <div
          className={`entry-card${mode === "self" ? " entry-card--selected" : ""}${joining ? " entry-card--disabled" : ""}`}
          role="button"
          tabIndex={0}
          onClick={() => setMode(mode === "self" ? "choose" : "self")}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setMode(mode === "self" ? "choose" : "self"); } }}
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
                autoFocus
              />
              <button
                className="entry-card-enter"
                onClick={() => handleSelf()}
                disabled={joining || !name.trim()}
              >
                {joining ? "Entering…" : "Enter →"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
