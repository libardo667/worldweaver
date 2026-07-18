// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useEffect, useState } from "react";
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
  const [place, setPlace] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const entryPlaces = entry?.locations ?? [];

  useEffect(() => {
    getTerms()
      .then((result) => setTermsText(result.terms))
      .catch(() => setTermsText(""));
  }, []);

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
    try {
      const auth =
        mode === "register"
          ? await postRegister({ email, username, display_name: displayName, password })
          : await postLogin(identifier, password);
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
      setError(err instanceof Error && err.message ? err.message : "That didn't work — try again.");
    } finally {
      setBusy(false);
    }
  }

  const registerReady = email && username && displayName && password.length >= 8 && termsAccepted;
  const loginReady = identifier && password;

  return (
    <div className="threshold">
      <div className="threshold-card join-card">
        <h1 className="threshold-title">Join the world</h1>
        <div className="join-tabs" role="tablist">
          <button role="tab" aria-selected={mode === "register"} className={mode === "register" ? "is-active" : ""} onClick={() => setMode("register")}>
            New here
          </button>
          <button role="tab" aria-selected={mode === "login"} className={mode === "login" ? "is-active" : ""} onClick={() => setMode("login")}>
            Coming back
          </button>
        </div>

        <form onSubmit={submit} className="join-form">
          {mode === "register" ? (
            <>
              <input type="email" placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
              <input placeholder="username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
              <input placeholder="name people will see" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
              <input type="password" placeholder="password (8+ characters)" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
              {termsText && (
                <label className="join-terms">
                  <input type="checkbox" checked={termsAccepted} onChange={(e) => setTermsAccepted(e.target.checked)} />
                  <span>{termsText}</span>
                </label>
              )}
            </>
          ) : (
            <>
              <input placeholder="username or email" value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoComplete="username" />
              <input type="password" placeholder="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
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

          {error && <p className="join-error">{error}</p>}

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
