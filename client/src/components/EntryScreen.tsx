import { useEffect, useState } from "react";
import { getWorldEntry, postSessionBootstrap, type EntryCard, type WorldEntryResponse } from "../api/wwClient";

type EntryScreenProps = {
  sessionId: string;
  onEnter: (entryAction: string) => void;
};

const KNOWN_LOCATIONS = [
  "cistern_rim",
  "silt_flats",
  "market_square",
  "greenhouse",
  "high_reach",
  "oakhaven_lows",
  "gray_river",
  "northern_intake",
];

export function EntryScreen({ sessionId, onEnter }: EntryScreenProps) {
  const [entry, setEntry] = useState<WorldEntryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [joining, setJoining] = useState(false);
  const [selected, setSelected] = useState<EntryCard | null>(null);
  const [customMode, setCustomMode] = useState(false);
  const [customName, setCustomName] = useState("");
  const [customRole, setCustomRole] = useState("");
  const [customLocation, setCustomLocation] = useState(KNOWN_LOCATIONS[0]);

  useEffect(() => {
    getWorldEntry()
      .then(setEntry)
      .catch(() => setEntry(null))
      .finally(() => setLoading(false));
  }, []);

  async function handleCardEnter(card: EntryCard) {
    if (joining || !entry?.world_id) return;
    setJoining(true);
    try {
      await postSessionBootstrap(sessionId, {
        world_id: entry.world_id,
        world_theme: "Oakhaven Lows",
        player_role: `${card.name} — ${card.role}`,
        entry_location: card.location,
        bootstrap_source: "entry-screen",
      });
      onEnter(card.entry_action);
    } catch {
      onEnter(card.entry_action);
    } finally {
      setJoining(false);
    }
  }

  async function handleCustomEnter() {
    const name = customName.trim();
    const role = customRole.trim();
    if (!name || !role || joining) return;
    setJoining(true);
    const action = `I arrive at the ${customLocation.replace(/_/g, " ")} as ${name}, ${role}.`;
    try {
      if (entry?.world_id) {
        await postSessionBootstrap(sessionId, {
          world_id: entry.world_id,
          world_theme: "Oakhaven Lows",
          player_role: `${name} — ${role}`,
          entry_location: customLocation,
          bootstrap_source: "entry-screen-custom",
        });
      }
      onEnter(action);
    } catch {
      onEnter(action);
    } finally {
      setJoining(false);
    }
  }

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

      <p className="entry-prompt">Who are you in this world?</p>

      <div className="entry-cards">
        {(entry?.cards ?? []).map((card, i) => (
          <div
            key={i}
            className={`entry-card${selected === card ? " entry-card--selected" : ""}${joining ? " entry-card--disabled" : ""}`}
            role="button"
            tabIndex={0}
            onClick={() => !joining && setSelected(selected === card ? null : card)}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (!joining) setSelected(selected === card ? null : card); } }}
          >
            <div className="entry-card-name">{card.name}</div>
            <div className="entry-card-role">{card.role}</div>
            <div className="entry-card-flavor">{card.flavor}</div>
            {selected === card && (
              <button
                className="entry-card-enter"
                onClick={(e) => { e.stopPropagation(); void handleCardEnter(card); }}
                disabled={joining}
              >
                {joining ? "Entering…" : "Enter as this character →"}
              </button>
            )}
          </div>
        ))}

        {/* Custom card */}
        <div
          className={`entry-card entry-card--custom${customMode ? " entry-card--selected" : ""}`}
          onClick={() => { setCustomMode(true); setSelected(null); }}
        >
          <div className="entry-card-name">Someone else</div>
          <div className="entry-card-role">Your own character</div>
          <div className="entry-card-flavor">Write who you are and where you arrive.</div>

          {customMode && (
            <div className="entry-custom-form" onClick={(e) => e.stopPropagation()}>
              <input
                className="entry-custom-input"
                placeholder="Your name"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                autoFocus
              />
              <input
                className="entry-custom-input"
                placeholder="Your role or description"
                value={customRole}
                onChange={(e) => setCustomRole(e.target.value)}
              />
              <select
                className="entry-custom-select"
                value={customLocation}
                onChange={(e) => setCustomLocation(e.target.value)}
              >
                {(entry?.cards
                  ? [...new Set([
                      ...entry.cards.map((c) => c.location).filter(Boolean),
                      ...KNOWN_LOCATIONS,
                    ])]
                  : KNOWN_LOCATIONS
                ).map((loc) => (
                  <option key={loc} value={loc}>
                    {loc.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
              <button
                className="entry-card-enter"
                onClick={() => void handleCustomEnter()}
                disabled={joining || !customName.trim() || !customRole.trim()}
              >
                {joining ? "Entering…" : "Enter as this character →"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
