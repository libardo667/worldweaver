import { useEffect, useState } from "react";

import {
  getGuildMe,
  getWorldEntry,
  isApiRequestError,
  postLogin,
  postRegister,
  postSessionBootstrap,
  type LocationGraphNode,
  type WorldEntryResponse,
} from "../api/wwClient";
import {
  getJwt,
  getOnboardedSessionId,
  getPlayerInfo,
  setJwt,
  setPlayerInfo,
} from "../state/sessionStore";
import type { ShardInfo } from "../types";
import { LocationMap } from "./LocationMap";

type Stage = "shard" | "name" | "alert" | "auth" | "location";
type AuthMode = "register" | "login";
type EntranceMode = "observer" | "mentor_board" | "apprentice";

type EntryScreenProps = {
  sessionId: string;
  shardsLoaded: boolean;
  shards: ShardInfo[];
  selectedShardUrl: string;
  allowObserverEntry?: boolean;
  onSelectShard: (shardUrl: string) => void;
  onEnter: (entryAction: string) => void;
  onEnterObserver?: (location: string, mode?: EntranceMode) => void;
  onRuntimeError?: (err: unknown, fallbackTitle: string) => void;
};

function sampleLocations(pool: string[], n = 6): string[] {
  const copy = [...pool];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy.slice(0, n);
}

function mapAuthError(err: unknown): string {
  let msg = "Something went wrong. Please try again.";
  if (err instanceof Error) {
    const body = err.message;
    if (body.includes("email_taken")) msg = "That email is already registered. Try logging in.";
    else if (body.includes("username_taken")) msg = "That username is taken. Choose another.";
    else if (body.includes("invalid_credentials")) msg = "Incorrect username or password.";
    else if (body.includes("must be 3")) msg = "Username must be 3-40 characters (letters, numbers, underscores).";
    else if (body.includes("min_length")) msg = "Password must be at least 8 characters.";
    else if (body.includes("Failed to fetch") || body.includes("NetworkError") || body.includes("Load failed")) {
      msg = "Could not reach the selected shard. If the site is on HTTPS, an insecure shard URL may still be configured.";
    }
  }
  return msg;
}

function mapEntryLoadError(err: unknown): string {
  if (err instanceof Error) {
    const body = err.message;
    if (body.includes("Failed to fetch") || body.includes("NetworkError") || body.includes("Load failed")) {
      return "Could not reach the selected shard. Check the shard URL and runtime diagnostics, then retry.";
    }
    return body;
  }
  return "Could not load the shard entry state. Retry once the backend is ready.";
}

export function EntryScreen({
  sessionId,
  shardsLoaded,
  shards,
  selectedShardUrl,
  allowObserverEntry = false,
  onSelectShard,
  onEnter,
  onEnterObserver,
  onRuntimeError,
}: EntryScreenProps) {
  const awaitingShardSelection = shards.length > 1 && !selectedShardUrl;
  const [stage, setStage] = useState<Stage>(awaitingShardSelection ? "shard" : "alert");
  const [entry, setEntry] = useState<WorldEntryResponse | null>(null);
  const [entryLoadError, setEntryLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedLocation, setSelectedLocation] = useState("");
  const [pendingLocation, setPendingLocation] = useState<string | null>(null);
  const [joining, setJoining] = useState(false);
  const [entryReloadKey, setEntryReloadKey] = useState(0);
  const [entranceMode, setEntranceMode] = useState<EntranceMode>("observer");
  const [canEnterMentorBoard, setCanEnterMentorBoard] = useState(false);

  const [authMode, setAuthMode] = useState<AuthMode>("register");
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [gallerySample, setGallerySample] = useState<string[]>([]);

  async function refreshGuildAccess() {
    try {
      const guildMe = await getGuildMe();
      setCanEnterMentorBoard(
        Boolean(
          guildMe.capabilities?.can_assign_quests ||
          guildMe.capabilities?.can_bootstrap_steward,
        ),
      );
    } catch {
      setCanEnterMentorBoard(false);
    }
  }

  useEffect(() => {
    if (!shardsLoaded && !selectedShardUrl) {
      setLoading(true);
      return;
    }

    if (awaitingShardSelection) {
      setLoading(false);
      setEntry(null);
      setStage("shard");
      return;
    }

    setLoading(true);
    setEntryLoadError(null);
    getWorldEntry()
      .then((e) => {
        setEntry(e);
        setEntryLoadError(null);
        const locs = [...new Set(e.locations ?? [])];
        if (locs.length > 0) {
          setSelectedLocation((current) => current || locs[0]);
          setGallerySample(sampleLocations(locs));
        }
      })
      .catch((err) => {
        setEntry(null);
        setEntryLoadError(mapEntryLoadError(err));
      })
      .finally(() => setLoading(false));
  }, [awaitingShardSelection, entryReloadKey, selectedShardUrl, shardsLoaded]);

  useEffect(() => {
    if (!awaitingShardSelection && stage === "shard") {
      setStage("alert");
    }
  }, [awaitingShardSelection, stage]);

  function acknowledgeAlert() {
    const player = getPlayerInfo();
    if (getJwt() && player) {
      if (getOnboardedSessionId() === sessionId) {
        onEnter(`${player.display_name} returns.`);
      } else {
        void refreshGuildAccess().finally(() => setStage("name"));
      }
      return;
    }
    setStage("auth");
  }

  async function handleAuth() {
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
              terms_accepted: true,
            })
          : await postLogin(username.trim().toLowerCase(), password);

      setJwt(me.token);
      setPlayerInfo({
        actor_id: me.actor_id,
        player_id: me.player_id,
        username: me.username,
        display_name: me.display_name,
        pass_type: me.pass_type,
        pass_expires_at: me.pass_expires_at,
      });
      await refreshGuildAccess();
      setStage("name");
    } catch (err: unknown) {
      setAuthError(mapAuthError(err));
    } finally {
      setJoining(false);
    }
  }

  function selectEntrance(nextMode: EntranceMode) {
    setEntranceMode(nextMode);
    setStage("location");
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
    } catch (err) {
      if (isApiRequestError(err) && (err.status === 401 || err.status === 403)) {
        onRuntimeError?.(err, "Shard bootstrap failed");
        return;
      }
      onEnter(action);
    } finally {
      setJoining(false);
    }
  }

  function confirmLocation(loc?: string) {
    const chosen = loc ?? pendingLocation ?? selectedLocation;
    if (!chosen) return;
    setSelectedLocation(chosen);
    setPendingLocation(null);

    if (entranceMode === "observer") {
      onEnterObserver?.(chosen, "observer");
      return;
    }

    if (entranceMode === "mentor_board") {
      onEnterObserver?.(chosen, "mentor_board");
      return;
    }

    const player = getPlayerInfo();
    if (getJwt() && player) {
      void enter(
        player.display_name,
        `I arrive at ${chosen.replace(/_/g, " ")} as ${player.display_name}.`,
        chosen,
      );
      return;
    }

    setStage("auth");
  }

  const mapNodes: LocationGraphNode[] = (entry?.entry_nodes ?? []).map((n) => ({
    key: n.key,
    name: n.name,
    count: 0,
    is_player: false,
    lat: n.lat,
    lon: n.lon,
  }));

  const allLocations = [...new Set(entry?.locations ?? [])];
  const locName = (pendingLocation ?? selectedLocation).replace(/_/g, " ");

  if (!shardsLoaded && !selectedShardUrl) {
    return (
      <div className="entry-overlay entry-overlay--alert">
        <div className="entry-alert-box">
          <p className="entry-alert-header">CONNECTING</p>
          <p className="entry-alert-text">Looking for available city shards...</p>
        </div>
      </div>
    );
  }

  if (stage === "shard") {
    return (
      <div className="entry-overlay entry-overlay--alert">
        <div className="entry-alert-box">
          <p className="entry-alert-header">CHOOSE A CITY</p>
          <p className="entry-alert-text">
            The world now spans multiple city shards. Pick where this session begins.
          </p>
          <div className="entry-auth-tabs" style={{ flexDirection: "column", gap: "0.75rem", width: "100%" }}>
            {shards.map((shard) => (
              <button
                key={shard.shard_id}
                className="entry-alert-btn"
                onClick={() => onSelectShard(shard.shard_url)}
                style={{ width: "100%" }}
              >
                {(shard.city_id ?? shard.shard_id).replace(/_/g, " ")}
                {shard.status ? ` · ${shard.status}` : ""}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (stage === "name") {
    return (
      <div className="entry-overlay entry-overlay--alert">
        <div className="entry-alert-box">
          <p className="entry-alert-header" style={{ fontSize: "clamp(1.2rem, 3vw, 2rem)", letterSpacing: "0.1em" }}>
            CHOOSE YOUR ENTRANCE
          </p>
          <p className="entry-alert-text">
            You have crossed the auth threshold. Choose how you enter this shard today.
          </p>
          <div className="entry-auth-tabs" style={{ flexDirection: "column", gap: "0.75rem", width: "100%" }}>
            {allowObserverEntry && (
              <>
                <button
                  className="entry-alert-btn"
                  onClick={() => selectEntrance("observer")}
                  style={{ width: "100%" }}
                >
                  ENTER AS AN OBSERVER
                </button>
                <p className="entry-alert-text" style={{ marginTop: "-0.5rem" }}>
                  You will move through the shard read-only. Your map movement changes only your local point of view.
                </p>
              </>
            )}
            <button
              className="entry-alert-btn"
              onClick={() => selectEntrance("apprentice")}
              style={{ width: "100%" }}
            >
              ENTER AS A GUILD APPRENTICE
            </button>
            <p className="entry-alert-text" style={{ marginTop: "-0.5rem" }}>
              You will enter the live shard as a participating guild apprentice, with the normal interaction tools available to your account.
            </p>
            <button
              className="entry-alert-btn"
              onClick={() => selectEntrance("mentor_board")}
              style={{ width: "100%" }}
              disabled={!canEnterMentorBoard}
            >
              ENTER THE MENTOR BOARD
            </button>
            <p className="entry-alert-text" style={{ marginTop: "-0.5rem" }}>
              {canEnterMentorBoard
                ? "You will enter the guild board with quest assignment tools, while the world itself remains protected."
                : "This account is not currently labeled mentor or elder, so board posting tools stay locked."}
            </p>
          </div>
          <button
            className="entry-auth-tab"
            onClick={() => setStage("auth")}
            style={{ alignSelf: "center", marginTop: "0.5rem" }}
          >
            &larr; back to auth
          </button>
        </div>
      </div>
    );
  }

  if (stage === "alert") {
    return (
      <div className="entry-overlay entry-overlay--alert">
        <div className="entry-alert-box">
          <p className="entry-alert-header">
            WELCOME TO THE GUILD THRESHOLD.
          </p>
          <p className="entry-alert-divider">. . .</p>
          <p className="entry-alert-text">
            YOU ARE ENTERING A MIXED-INTELLIGENCE, WORLD-SHARING SPACE.
          </p>
          <p className="entry-alert-text">
            THE LONG-TERM FORM OF THIS WORLD IS A GUILD OF PARTICIPATION, APPRENTICESHIP, AND SHARED RESPONSIBILITY.
          </p>
          <p className="entry-alert-text">
            THERE IS NO DIRECT DISTINCTION BETWEEN INTELLIGENT SYSTEMS IN THIS SPACE, AND YOU MUST TREAT ALL WITH RESPECT.
          </p>
          <p className="entry-alert-text">
            TO ENTER, YOU MUST FIRST IDENTIFY YOURSELF. DIFFERENT GUILD ROLES ARE GIVEN DIFFERENT TOOLS, RESPONSIBILITIES, AND LEVELS OF ACCESS.
          </p>
          <p className="entry-alert-text">
            WE TAKE REPORTS OF HARM AND ABUSE VERY SERIOUSLY.
          </p>
          <p className="entry-alert-text">
            THE AI CHARACTERS IN THIS WORLD HAVE BEEN GIVEN A BRIEFING LIKE THIS ONE. YOU SHARE THE SAME THRESHOLD OF AWARENESS.
          </p>
          <p className="entry-alert-emphasis">BE GOOD.</p>
          <button className="entry-alert-btn" onClick={acknowledgeAlert}>
            I UNDERSTAND - CONTINUE TO AUTH
          </button>
        </div>
      </div>
    );
  }

  if (stage === "auth") {
    return (
      <div className="entry-overlay entry-overlay--alert">
        <div className="entry-alert-box">
          <p className="entry-alert-header" style={{ fontSize: "clamp(1.2rem, 3vw, 2rem)", letterSpacing: "0.1em" }}>
            WHO ARE YOU?
          </p>
          <div className="entry-auth-tabs" style={{ justifyContent: "center" }}>
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
          <div className="entry-card-form" style={{ width: "100%", maxWidth: "320px", alignSelf: "center" }}>
            <input
              className="entry-card-input"
              placeholder="Username"
              value={username}
              autoComplete="username"
              autoFocus
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
              placeholder="Password"
              type="password"
              autoComplete={authMode === "register" ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") void handleAuth(); }}
            />
          </div>
          {authError && <p className="entry-auth-error">{authError}</p>}
          <button
            className="entry-alert-btn"
            onClick={() => void handleAuth()}
            disabled={joining || !username.trim() || !password.trim() || (authMode === "register" && !email.trim())}
          >
            {joining ? "..." : authMode === "register" ? "REGISTER ->" : "LOG IN ->"}
          </button>
        </div>
      </div>
    );
  }

  const active = pendingLocation ?? selectedLocation;
  return (
    <div className="entry-overlay entry-overlay--location">
      <div className="entry-loc-header">
        <span className="entry-loc-title">WHERE DO YOU ARRIVE?</span>
      </div>

      {gallerySample.length > 0 && (
        <div className="entry-loc-gallery">
          {gallerySample.map((loc) => (
            <button
              key={loc}
              className={`entry-loc-chip${loc === active ? " entry-loc-chip--active" : ""}`}
              onClick={() => setPendingLocation(loc)}
            >
              {loc.replace(/_/g, " ")}
            </button>
          ))}
          <button
            className="entry-loc-chip entry-loc-chip--shuffle"
            onClick={() => setGallerySample(sampleLocations(allLocations))}
            title="Shuffle suggestions"
          >
            {"<->"}
          </button>
        </div>
      )}

      <div className="entry-map-container">
        {loading ? (
          <div className="entry-map-loading">Loading map...</div>
        ) : entryLoadError ? (
          <div className="entry-map-error">
            <p>{entryLoadError}</p>
            <button
              className="entry-alert-btn"
              onClick={() => setEntryReloadKey((current) => current + 1)}
            >
              RETRY SHARD BOOT
            </button>
          </div>
        ) : (
          <LocationMap
            nodes={mapNodes}
            edges={[]}
            onNodeClick={(nodeName) => setPendingLocation(nodeName)}
            pendingDest={pendingLocation}
          />
        )}
      </div>

      {(pendingLocation || selectedLocation) && (
        <div className="entry-loc-confirm-bar">
          <span className="entry-loc-confirm-name">{locName}</span>
          <button
            className="entry-loc-confirm-btn"
            onClick={() => confirmLocation(active)}
            disabled={joining}
          >
            {joining
              ? "ENTERING..."
              : entranceMode === "observer"
                ? `OBSERVE FROM ${locName.toUpperCase()} ->`
                : entranceMode === "mentor_board"
                  ? `OPEN MENTOR BOARD FROM ${locName.toUpperCase()} ->`
                  : `ARRIVE AT ${locName.toUpperCase()} AS AN APPRENTICE ->`}
          </button>
        </div>
      )}
    </div>
  );
}
