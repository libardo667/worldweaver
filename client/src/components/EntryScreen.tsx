import { useEffect, useState } from "react";
import {
  getWorldEntry,
  postSessionBootstrap,
  postRegister,
  postLogin,
  type WorldEntryResponse,
} from "../api/wwClient";
import { setJwt, setPlayerInfo } from "../state/sessionStore";
import { LocationMap } from "./LocationMap";
import type { LocationGraphNode } from "../api/wwClient";

const ALERT_STORAGE_KEY = "ww_entry_alert_acknowledged";

type Stage = "alert" | "location" | "cards";
type AuthMode = "register" | "login";

type EntryScreenProps = {
  sessionId: string;
  onEnter: (entryAction: string) => void;
};

export function EntryScreen({ sessionId, onEnter }: EntryScreenProps) {
  const [stage, setStage] = useState<Stage>(
    () => (localStorage.getItem(ALERT_STORAGE_KEY) === "1" ? "location" : "alert")
  );
  const [entry, setEntry] = useState<WorldEntryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedLocation, setSelectedLocation] = useState<string>("");
  const [pendingLocation, setPendingLocation] = useState<string | null>(null);
  const [joining, setJoining] = useState(false);

  // Auth card state
  const [authMode, setAuthMode] = useState<AuthMode>("register");
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);

  // Quick Start (BYOK) card state
  const [bringName, setBringName] = useState("");
  const [apiKey, setApiKey] = useState("");

  useEffect(() => {
    getWorldEntry()
      .then((e) => {
        setEntry(e);
        if (e.locations?.length) setSelectedLocation(e.locations[0]);
      })
      .catch(() => setEntry(null))
      .finally(() => setLoading(false));
  }, []);

  function acknowledgeAlert() {
    localStorage.setItem(ALERT_STORAGE_KEY, "1");
    setStage("location");
  }

  function handleMapNodeClick(nodeName: string) {
    setPendingLocation(nodeName);
  }

  function confirmLocation(loc?: string) {
    const chosen = loc ?? pendingLocation ?? selectedLocation;
    if (chosen) setSelectedLocation(chosen);
    setPendingLocation(null);
    setStage("cards");
  }

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

  async function enterAsVisitor() {
    if (joining) return;
    setAuthError(null);
    setJoining(true);
    try {
      const me =
        authMode === "register"
          ? await postRegister({
              email,
              username: username.trim().toLowerCase(),
              display_name: displayName.trim() || username.trim(),
              password,
              pass_type: "visitor_7day",
              terms_accepted: true, // user acknowledged terms in stage 1
            })
          : await postLogin(username.trim().toLowerCase(), password);

      setJwt(me.token);
      setPlayerInfo({
        player_id: me.player_id,
        username: me.username,
        display_name: me.display_name,
        pass_type: me.pass_type,
        pass_expires_at: me.pass_expires_at,
      });

      const name = me.display_name;
      await enter(name, `I arrive at ${confirmedLocName} as ${name}.`, selectedLocation);
    } catch (err: unknown) {
      setJoining(false);
      let msg = "Something went wrong. Please try again.";
      if (err instanceof Error) {
        const body = err.message;
        if (body.includes("email_taken")) msg = "That email is already registered. Try logging in.";
        else if (body.includes("username_taken")) msg = "That username is taken. Choose another.";
        else if (body.includes("invalid_credentials")) msg = "Incorrect username or password.";
        else if (body.includes("must be 3")) msg = "Username must be 3–40 characters (letters, numbers, underscores).";
        else if (body.includes("min_length")) msg = "Password must be at least 8 characters.";
      }
      setAuthError(msg);
    }
  }

  // Map entry_nodes → LocationGraphNode[] for LocationMap
  const mapNodes: LocationGraphNode[] = (entry?.entry_nodes ?? []).map((n) => ({
    key: n.key,
    name: n.name,
    count: 0,
    is_player: false,
    lat: n.lat,
    lon: n.lon,
  }));

  const locName = (pendingLocation ?? selectedLocation).replace(/_/g, " ");
  const confirmedLocName = selectedLocation.replace(/_/g, " ");
  const locations = entry?.locations ?? [];

  // ── Stage 1: Alert ────────────────────────────────────────────────────────

  if (stage === "alert") {
    return (
      <div className="entry-overlay entry-overlay--alert">
        <div className="entry-alert-box">
          <p className="entry-alert-header">ALERT</p>
          <p className="entry-alert-text">
            YOU ARE ENTERING A MIXED-INTELLIGENCE, WORLD-SHARING SPACE.
          </p>
          <p className="entry-alert-text">
            THERE IS NO DIRECT DISTINCTION BETWEEN INTELLIGENT SYSTEMS IN THIS
            SPACE, AND YOU MUST TREAT ALL WITH RESPECT.
          </p>
          <p className="entry-alert-text">
            BY ENTERING THIS SPACE AS MORE THAN AN OBSERVER, YOU AGREE TO OUR
            TERMS OF USE, WHICH INCLUDES MONITORING LOGS MADE IN PUBLIC SPACES.
          </p>
          <p className="entry-alert-text">
            WE TAKE REPORTS OF HARM AND ABUSE VERY SERIOUSLY.
          </p>
          <p className="entry-alert-emphasis">BE GOOD.</p>
          <button className="entry-alert-btn" onClick={acknowledgeAlert}>
            I UNDERSTAND — ENTER
          </button>
        </div>
      </div>
    );
  }

  // ── Stage 2: Location ─────────────────────────────────────────────────────

  if (stage === "location") {
    return (
      <div className="entry-overlay entry-overlay--location">
        <div className="entry-loc-header">
          <span className="entry-loc-title">WHERE DO YOU ARRIVE?</span>
          <div className="entry-loc-controls">
            {locations.length > 0 && (
              <select
                className="entry-loc-dropdown"
                value={pendingLocation ?? selectedLocation}
                onChange={(e) => setPendingLocation(e.target.value)}
              >
                {locations.map((loc) => (
                  <option key={loc} value={loc}>
                    {loc.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            )}
            <button
              className="entry-loc-btn"
              onClick={() => confirmLocation()}
              disabled={!selectedLocation && !pendingLocation}
            >
              ARRIVE HERE →
            </button>
          </div>
        </div>

        <div className="entry-map-container">
          {loading ? (
            <div className="entry-map-loading">Loading map…</div>
          ) : (
            <LocationMap
              nodes={mapNodes}
              edges={[]}
              onNodeClick={handleMapNodeClick}
              pendingDest={pendingLocation}
            />
          )}
        </div>

        {pendingLocation && (
          <div className="entry-loc-confirm-bar">
            <span className="entry-loc-confirm-name">{locName}</span>
            <button
              className="entry-loc-confirm-btn"
              onClick={() => confirmLocation(pendingLocation)}
            >
              ARRIVE AT {locName.toUpperCase()} →
            </button>
          </div>
        )}
      </div>
    );
  }

  // ── Stage 3: Cards ────────────────────────────────────────────────────────

  return (
    <div className="entry-overlay entry-overlay--cards">
      <div className="entry-cards-modal">
        <p className="entry-cards-location">
          Arriving at <strong>{confirmedLocName}</strong>
          <button
            className="entry-cards-change-loc"
            onClick={() => setStage("location")}
          >
            ← change
          </button>
        </p>
        <h2 className="entry-cards-title">HOW DO YOU ENTER?</h2>

        <div className="entry-cards-grid">
          {/* Observer */}
          <div className="entry-card entry-card--observer">
            <div className="entry-card-badge">OBSERVER</div>
            <div className="entry-card-name">Ghost presence</div>
            <div className="entry-card-flavor">
              Unnamed. No agency, no chat. You appear as one of the quiet
              figures present in a space. Watch and listen without leaving a
              trace.
            </div>
            <button
              className="entry-card-btn"
              onClick={() =>
                enter(
                  "an observer",
                  `I arrive at ${confirmedLocName}, observing quietly.`,
                  selectedLocation,
                )
              }
              disabled={joining}
            >
              {joining ? "Entering…" : "ENTER AS OBSERVER"}
            </button>
          </div>

          {/* 7-day visitor — register / login */}
          <div className="entry-card entry-card--visitor">
            <div className="entry-card-badge">7-DAY VISITOR PASS</div>
            <div className="entry-card-name">Full presence</div>
            <div className="entry-card-flavor">
              Full agency. Speak, act, be remembered. Your session persists
              across refreshes. Default models provided.
            </div>

            {/* Register / Login toggle */}
            <div className="entry-auth-tabs">
              <button
                className={`entry-auth-tab${authMode === "register" ? " active" : ""}`}
                onClick={() => { setAuthMode("register"); setAuthError(null); }}
              >
                Register
              </button>
              <button
                className={`entry-auth-tab${authMode === "login" ? " active" : ""}`}
                onClick={() => { setAuthMode("login"); setAuthError(null); }}
              >
                Log in
              </button>
            </div>

            <div className="entry-card-form">
              <input
                className="entry-card-input"
                placeholder="Username (login handle)"
                value={username}
                autoComplete="username"
                onChange={(e) => setUsername(e.target.value)}
              />
              {authMode === "register" && (
                <>
                  <input
                    className="entry-card-input"
                    placeholder="Display name (in-world name)"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                  />
                  <input
                    className="entry-card-input"
                    placeholder="Email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </>
              )}
              <input
                className="entry-card-input"
                placeholder="Password (min 8 chars)"
                type="password"
                autoComplete={authMode === "register" ? "new-password" : "current-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") void enterAsVisitor(); }}
              />
            </div>

            {authError && (
              <p className="entry-auth-error">{authError}</p>
            )}

            <button
              className="entry-card-btn entry-card-btn--primary"
              onClick={() => void enterAsVisitor()}
              disabled={joining || !username.trim() || !password.trim() || (authMode === "register" && !email.trim())}
            >
              {joining ? "Entering…" : authMode === "register" ? "REGISTER & ENTER →" : "LOG IN & ENTER →"}
            </button>
          </div>

          {/* Quick Start — BYOK */}
          <div className="entry-card entry-card--quickstart">
            <div className="entry-card-badge">QUICK START</div>
            <div className="entry-card-name">Bring your own key</div>
            <div className="entry-card-flavor">
              Provide your API key. No account needed. Your narrative weight
              persists for this session.
            </div>
            <div className="entry-card-form">
              <input
                className="entry-card-input"
                placeholder="Name / handle"
                value={bringName}
                onChange={(e) => setBringName(e.target.value)}
              />
              <input
                className="entry-card-input"
                placeholder="API key"
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
            </div>
            <button
              className="entry-card-btn entry-card-btn--accent"
              onClick={() =>
                enter(
                  bringName.trim() || "a citizen",
                  `I arrive at ${confirmedLocName}${bringName.trim() ? ` as ${bringName.trim()}` : ""}.`,
                  selectedLocation,
                )
              }
              disabled={joining || !bringName.trim()}
            >
              {joining ? "Entering…" : "BEGIN →"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
