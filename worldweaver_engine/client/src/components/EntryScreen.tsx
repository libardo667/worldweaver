import { useEffect, useState } from "react";

import {
  getWorldEntry,
  isApiRequestError,
  postLogin,
  postRequestPasswordReset,
  postRegister,
  postResetPassword,
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

type Stage = "shard" | "threshold" | "auth" | "location";
type AuthMode = "register" | "login" | "reset";
type EntranceMode = "observer" | "apprentice";

type EntryScreenProps = {
  sessionId: string;
  shardsLoaded: boolean;
  shards: ShardInfo[];
  selectedShardUrl: string;
  allowObserverEntry?: boolean;
  initialIntent?: "join" | null;
  onConsumeInitialIntent?: () => void;
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
    else if (body.includes("invalid_credentials")) msg = "Incorrect username/email or password.";
    else if (body.includes("invalid_reset_token")) msg = "That reset token is invalid.";
    else if (body.includes("expired_reset_token")) msg = "That reset token has expired. Request a new one.";
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
  initialIntent = null,
  onConsumeInitialIntent,
  onSelectShard,
  onEnter,
  onEnterObserver,
  onRuntimeError,
}: EntryScreenProps) {
  const awaitingShardSelection = shards.length > 1 && !selectedShardUrl;
  const [stage, setStage] = useState<Stage>(awaitingShardSelection ? "shard" : "threshold");
  const [entry, setEntry] = useState<WorldEntryResponse | null>(null);
  const [entryLoadError, setEntryLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedLocation, setSelectedLocation] = useState("");
  const [pendingLocation, setPendingLocation] = useState<string | null>(null);
  const [joining, setJoining] = useState(false);
  const [entryReloadKey, setEntryReloadKey] = useState(0);
  const [entranceMode, setEntranceMode] = useState<EntranceMode>("observer");

  const [authMode, setAuthMode] = useState<AuthMode>("register");
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [resetStatus, setResetStatus] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [gallerySample, setGallerySample] = useState<string[]>([]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const token = params.get("reset_token");
    if (token) {
      setAuthMode("reset");
      setResetToken(token);
    }
  }, []);

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
      setStage("threshold");
    }
  }, [awaitingShardSelection, stage]);

  function enterQuietly() {
    setEntranceMode("observer");
    setStage("location");
  }

  function joinTheWorld() {
    const player = getPlayerInfo();
    if (getJwt() && player) {
      if (getOnboardedSessionId() === sessionId) {
        onEnter(`${player.display_name} returns.`);
      } else {
        setEntranceMode("apprentice");
        setStage("location");
      }
      return;
    }
    setStage("auth");
  }

  useEffect(() => {
    if (initialIntent !== "join" || stage !== "threshold") return;
    joinTheWorld();
    onConsumeInitialIntent?.();
  }, [initialIntent, onConsumeInitialIntent, stage]);

  async function handleAuth() {
    if (joining) return;
    setAuthError(null);
    setResetStatus(null);
    setJoining(true);
    try {
      if (authMode === "reset") {
        const me = await postResetPassword({
          token: resetToken.trim(),
          new_password: newPassword,
        });
        setJwt(me.token);
        setPlayerInfo({
          actor_id: me.actor_id,
          player_id: me.player_id,
          username: me.username,
          display_name: me.display_name,
          pass_type: me.pass_type,
          pass_expires_at: me.pass_expires_at,
        });
        setPassword("");
        setNewPassword("");
        setResetStatus("Password reset complete. You are now signed in.");
        setEntranceMode("apprentice");
        setStage("location");
        return;
      }

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
      setEntranceMode("apprentice");
      setStage("location");
    } catch (err: unknown) {
      setAuthError(mapAuthError(err));
    } finally {
      setJoining(false);
    }
  }

  async function handleRequestPasswordReset() {
    if (joining || !username.trim()) return;
    setJoining(true);
    setAuthError(null);
    setResetStatus(null);
    try {
      await postRequestPasswordReset(username.trim().toLowerCase());
      setResetStatus("If that account exists, a reset token has been sent to its email. Paste the token below to choose a new password.");
    } catch (err: unknown) {
      setAuthError(mapAuthError(err));
    } finally {
      setJoining(false);
    }
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
          <p className="entry-alert-header">Connecting</p>
          <p className="entry-alert-text">Looking for available city shards...</p>
        </div>
      </div>
    );
  }

  if (stage === "shard") {
    return (
      <div className="entry-overlay entry-overlay--alert">
        <div className="entry-alert-box">
          <p className="entry-alert-header">Choose a city</p>
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

  if (stage === "threshold") {
    return (
      <div className="entry-overlay entry-overlay--alert">
        <div className="entry-alert-box">
          <p className="entry-alert-header" style={{ fontSize: "clamp(1.35rem, 3vw, 2.2rem)", letterSpacing: "0.06em" }}>
            Enter a world already in progress
          </p>
          <p className="entry-alert-text">
            WorldWeaver is a shared place inhabited by humans and AI residents. It continues whether or not you are here.
          </p>
          <p className="entry-alert-text">
            You can step inside quietly, or join as yourself and take part.
          </p>
          <div className="entry-auth-tabs" style={{ flexDirection: "column", gap: "0.75rem", width: "100%", marginTop: "0.75rem" }}>
            {allowObserverEntry && (
              <button className="entry-alert-btn" onClick={enterQuietly} style={{ width: "100%" }}>
                Look around
              </button>
            )}
            <button className="entry-alert-btn" onClick={joinTheWorld} style={{ width: "100%" }}>
              Join the world
            </button>
          </div>
          <p className="entry-alert-text" style={{ marginTop: "0.75rem" }}>
            Quiet does not mean empty. Move gently through a shared place.
          </p>
        </div>
      </div>
    );
  }

  if (stage === "auth") {
    return (
      <div className="entry-overlay entry-overlay--alert">
        <div className="entry-alert-box">
          <p className="entry-alert-header" style={{ fontSize: "clamp(1.2rem, 3vw, 2rem)", letterSpacing: "0.1em" }}>
            Join as yourself
          </p>
          <p className="entry-alert-text" style={{ maxWidth: "32rem", textAlign: "center" }}>
            Create a persistent identity so the world can remember you when you return.
          </p>
          <div className="entry-auth-tabs" style={{ justifyContent: "center" }}>
            <button
              className={`entry-auth-tab${authMode === "register" ? " active" : ""}`}
              onClick={() => { setAuthMode("register"); setAuthError(null); setResetStatus(null); }}
            >
              Register
            </button>
            <button
              className={`entry-auth-tab${authMode === "login" ? " active" : ""}`}
              onClick={() => { setAuthMode("login"); setAuthError(null); setResetStatus(null); }}
            >
              Log in
            </button>
            <button
              className={`entry-auth-tab${authMode === "reset" ? " active" : ""}`}
              onClick={() => { setAuthMode("reset"); setAuthError(null); setResetStatus(null); }}
            >
              Reset password
            </button>
          </div>
          <div className="entry-card-form" style={{ width: "100%", maxWidth: "320px", alignSelf: "center" }}>
            <input
              className="entry-card-input"
              placeholder={authMode === "login" ? "Username or email" : authMode === "reset" ? "Username or email for reset" : "Username"}
              value={username}
              autoComplete={authMode === "reset" ? "username email" : "username"}
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
            {authMode !== "reset" && (
              <>
                <input
                  className="entry-card-input"
                  placeholder="Password"
                  type={showPassword ? "text" : "password"}
                  autoComplete={authMode === "register" ? "new-password" : "current-password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") void handleAuth(); }}
                />
                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.88rem", opacity: 0.85 }}>
                  <input type="checkbox" checked={showPassword} onChange={(e) => setShowPassword(e.target.checked)} />
                  Show password
                </label>
              </>
            )}
            {authMode === "reset" && (
              <>
                <button
                  className="entry-auth-tab"
                  onClick={() => void handleRequestPasswordReset()}
                  disabled={joining || !username.trim()}
                  style={{ alignSelf: "flex-start" }}
                >
                  {joining ? "Sending..." : "Email reset token"}
                </button>
                <input
                  className="entry-card-input"
                  placeholder="Reset token"
                  value={resetToken}
                  onChange={(e) => setResetToken(e.target.value)}
                />
                <input
                  className="entry-card-input"
                  placeholder="New password"
                  type={showNewPassword ? "text" : "password"}
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") void handleAuth(); }}
                />
                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.88rem", opacity: 0.85 }}>
                  <input type="checkbox" checked={showNewPassword} onChange={(e) => setShowNewPassword(e.target.checked)} />
                  Show new password
                </label>
              </>
            )}
          </div>
          {resetStatus && <p className="entry-alert-text" style={{ maxWidth: "320px", textAlign: "center" }}>{resetStatus}</p>}
          {authError && <p className="entry-auth-error">{authError}</p>}
          <button
            className="entry-alert-btn"
            onClick={() => void handleAuth()}
            disabled={
              joining ||
              !username.trim() ||
              (authMode === "register" && (!password.trim() || !email.trim())) ||
              (authMode === "login" && !password.trim()) ||
              (authMode === "reset" && (!resetToken.trim() || !newPassword.trim()))
            }
          >
            {joining
              ? "..."
              : authMode === "register"
                ? "REGISTER ->"
                : authMode === "login"
                  ? "LOG IN ->"
                  : "RESET PASSWORD ->"}
          </button>
          {authMode === "login" && (
            <button
              className="entry-auth-tab"
              onClick={() => { setAuthMode("reset"); setAuthError(null); setResetStatus(null); }}
              style={{ alignSelf: "center", marginTop: "0.5rem" }}
            >
              Forgot your password?
            </button>
          )}
        </div>
      </div>
    );
  }

  const active = pendingLocation ?? selectedLocation;
  const locationTitle =
    entranceMode === "observer"
      ? "Where would you like to arrive?"
      : "Where would you like to begin?";
  const locationHelper =
    entranceMode === "observer"
      ? "As an observer, you can move, watch, and listen without speaking or altering the world."
      : "You can start anywhere. The world will remember where you entered.";
  return (
    <div className="entry-overlay entry-overlay--location">
      <div className="entry-loc-header">
        <span className="entry-loc-title">{locationTitle}</span>
      </div>
      <p className="entry-alert-text" style={{ margin: "0 auto 1rem", maxWidth: "42rem", textAlign: "center" }}>
        {locationHelper}
      </p>

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
                ? `Enter quietly from ${locName} ->`
                : `Enter the world from ${locName} ->`}
          </button>
        </div>
      )}
    </div>
  );
}
