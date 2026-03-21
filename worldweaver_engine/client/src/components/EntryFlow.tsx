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
import { AuthScreen } from "./AuthScreen";
import { LocationChooserScreen } from "./LocationChooserScreen";
import { ParticipationModeScreen } from "./ParticipationModeScreen";
import { ShardSelectScreen } from "./ShardSelectScreen";
import { ThresholdScreen } from "./ThresholdScreen";

type Stage = "shard" | "threshold" | "auth" | "location";
export type AuthMode = "register" | "login" | "reset";
export type EntranceMode = "observer" | "apprentice";

export type EntryScreenProps = {
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

export function EntryFlow({
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
      <ShardSelectScreen
        shards={shards}
        onSelectShard={onSelectShard}
      />
    );
  }

  if (stage === "threshold") {
    return (
      <ThresholdScreen
        actions={
          <ParticipationModeScreen
            allowObserverEntry={allowObserverEntry}
            onLookAround={enterQuietly}
            onJoinTheWorld={joinTheWorld}
          />
        }
      />
    );
  }

  if (stage === "auth") {
    return (
      <AuthScreen
        authMode={authMode}
        username={username}
        displayName={displayName}
        email={email}
        password={password}
        showPassword={showPassword}
        resetToken={resetToken}
        newPassword={newPassword}
        showNewPassword={showNewPassword}
        resetStatus={resetStatus}
        authError={authError}
        joining={joining}
        onAuthModeChange={(nextMode) => {
          setAuthMode(nextMode);
          setAuthError(null);
          setResetStatus(null);
        }}
        onUsernameChange={setUsername}
        onDisplayNameChange={setDisplayName}
        onEmailChange={setEmail}
        onPasswordChange={setPassword}
        onShowPasswordChange={setShowPassword}
        onResetTokenChange={setResetToken}
        onNewPasswordChange={setNewPassword}
        onShowNewPasswordChange={setShowNewPassword}
        onSubmit={() => void handleAuth()}
        onRequestResetToken={() => void handleRequestPasswordReset()}
      />
    );
  }

  return (
    <LocationChooserScreen
      entranceMode={entranceMode}
      loading={loading}
      joining={joining}
      entryLoadError={entryLoadError}
      pendingLocation={pendingLocation}
      selectedLocation={selectedLocation}
      gallerySample={gallerySample}
      mapNodes={mapNodes}
      onPendingLocationChange={setPendingLocation}
      onShuffleGallery={() => setGallerySample(sampleLocations(allLocations))}
      onRetryEntryLoad={() => setEntryReloadKey((current) => current + 1)}
      onConfirmLocation={confirmLocation}
    />
  );
}
