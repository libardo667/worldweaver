// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { getTerms, postLogin, postRegister, postSessionBootstrap } from "../api/ww";
import type { EntryInfo } from "../api/types";
import { getPlayer, mintSessionId, setJwt, setPlayer, setStandingPlace } from "../session/store";

type Props = {
  entry: EntryInfo | null;
  /** Place carried from the map (?place= or the last-looked-at place). */
  suggestedPlace: string | null;
  onJoined: (place: string, displayName: string) => void;
  onClose: () => void;
};

type Mode = "register" | "login";

/**
 * Native join: make or recall an identity, then step into the world at a
 * chosen entry place. One card, no ceremony; the terms are the shard's own.
 */
export function JoinFlow({ entry, suggestedPlace, onJoined, onClose }: Props) {
  const [mode, setMode] = useState<Mode>(getPlayer() ? "login" : "register");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [identifier, setIdentifier] = useState(getPlayer()?.username ?? "");
  const [termsText, setTermsText] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [termsLoading, setTermsLoading] = useState(true);
  const [termsError, setTermsError] = useState("");
  const [place, setPlace] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const entryPlaces = entry?.locations ?? [];

  const loadTerms = useCallback(async () => {
    setTermsLoading(true);
    setTermsError("");
    setTermsAccepted(false);
    try {
      const result = await getTerms();
      const terms = String(result.terms ?? "").trim();
      if (!terms) throw new Error("The shard returned empty terms.");
      setTermsText(terms);
    } catch {
      setTermsText("");
      setTermsError("This shard's terms could not be loaded. Registration is paused until you can read them.");
    } finally {
      setTermsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTerms();
  }, [loadTerms]);

  useEffect(() => {
    if (place) return;
    if (suggestedPlace && entryPlaces.includes(suggestedPlace)) {
      setPlace(suggestedPlace);
    } else if (entryPlaces.length > 0) {
      setPlace(entryPlaces[0]);
    }
  }, [suggestedPlace, entryPlaces, place]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || !entry || !place) return;
    setBusy(true);
    setError("");
    let newlyRegisteredUsername = "";
    try {
      const auth =
        mode === "register"
          ? await postRegister({ email, username, display_name: displayName, password, terms_accepted: termsAccepted })
          : await postLogin(identifier, password);
      if (mode === "register") newlyRegisteredUsername = auth.username;
      setJwt(auth.token);
      setPlayer({
        actor_id: auth.actor_id,
        player_id: auth.player_id,
        username: auth.username,
        display_name: auth.display_name,
      });
      const sessionId = mintSessionId();
      await postSessionBootstrap(sessionId, entry.world_id, auth.display_name, place);
      setStandingPlace(place);
      onJoined(place, auth.display_name);
    } catch (err) {
      if (newlyRegisteredUsername) {
        setMode("login");
        setIdentifier(newlyRegisteredUsername);
        setError("Your account was created, but the shard did not let you enter. Try again under Coming back.");
      } else {
        setError(err instanceof Error && err.message ? err.message : "That didn't work — try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  const registerReady = email && username && displayName && password.length >= 8 && termsText && termsAccepted && !termsLoading && !termsError;
  const loginReady = identifier && password;

  return (
    <div className="threshold">
      <div className="threshold-card join-card" role="dialog" aria-labelledby="join-title">
        <h1 id="join-title" className="threshold-title">Join the world</h1>
        <div className="join-tabs" aria-label="Choose how to join">
          <button type="button" aria-pressed={mode === "register"} className={mode === "register" ? "is-active" : ""} onClick={() => setMode("register")}>
            New here
          </button>
          <button type="button" aria-pressed={mode === "login"} className={mode === "login" ? "is-active" : ""} onClick={() => setMode("login")}>
            Coming back
          </button>
        </div>

        <form onSubmit={submit} className="join-form">
          {mode === "register" ? (
            <>
              <label className="sr-only" htmlFor="join-email">Email</label>
              <input id="join-email" type="email" placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
              <label className="sr-only" htmlFor="join-username">Username</label>
              <input id="join-username" placeholder="username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
              <label className="sr-only" htmlFor="join-display-name">Name people will see</label>
              <input id="join-display-name" placeholder="name people will see" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
              <label className="sr-only" htmlFor="join-new-password">Password, at least 8 characters</label>
              <input id="join-new-password" type="password" placeholder="password (8+ characters)" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
              {termsLoading && <p className="place-empty">Loading this shard's terms…</p>}
              {termsError && (
                <div>
                  <p className="join-error" role="alert">{termsError}</p>
                  <button type="button" className="btn btn-quiet" onClick={() => void loadTerms()}>
                    Try loading them again
                  </button>
                </div>
              )}
              {!termsLoading && !termsError && termsText && (
                <label className="join-terms">
                  <input type="checkbox" checked={termsAccepted} onChange={(e) => setTermsAccepted(e.target.checked)} />
                  <span>{termsText}</span>
                </label>
              )}
            </>
          ) : (
            <>
              <label className="sr-only" htmlFor="join-identifier">Username or email</label>
              <input id="join-identifier" placeholder="username or email" value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoComplete="username" />
              <label className="sr-only" htmlFor="join-password">Password</label>
              <input id="join-password" type="password" placeholder="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            </>
          )}

          {entryPlaces.length > 0 && (
            <div className="join-places">
              <p className="join-places-label">You'll arrive at</p>
              <div className="walk-targets">
                {entryPlaces.map((name) => (
                  <button type="button" key={name} className={`walk-target${place === name ? " is-chosen" : ""}`} onClick={() => setPlace(name)}>
                    {name}
                  </button>
                ))}
              </div>
            </div>
          )}

          {error && <p className="join-error" role="alert">{error}</p>}

          <div className="threshold-actions">
            <button type="submit" className="btn btn-primary" disabled={busy || !place || !(mode === "register" ? registerReady : loginReady)}>
              {busy ? "Stepping in…" : "Step into the world"}
            </button>
            <button type="button" className="btn btn-quiet" onClick={onClose}>
              Just look around instead
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
