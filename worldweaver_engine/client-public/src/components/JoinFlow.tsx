// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  ApiError,
  getCurrentSession,
  getTerms,
  patchProfile,
  postLogin,
  postRegister,
  postResendVerification,
  postRequestPasswordReset,
  postResetPassword,
  postSessionBootstrap,
  postVerifyEmail,
} from "../api/ww";
import type { AuthResponse, EntryInfo } from "../api/types";
import {
  getPlayer,
  mintSessionId,
  setJwt,
  setPlayer,
  setSessionId,
  setStandingPlace,
} from "../session/store";

type Props = {
  entry: EntryInfo | null;
  /** Place carried from the map (?place= or the last-looked-at place). */
  suggestedPlace: string | null;
  onJoined: (place: string, displayName: string) => void;
  onClose: () => void;
  /** Authenticate an actor who already has a federation trip in progress. */
  arrival?: { onAuthenticated: () => Promise<void> };
};

type Mode = "register" | "verify" | "profile" | "login" | "reset";

/**
 * Native join: make or recall an identity, then step into the world at a
 * chosen entry place. One card, no ceremony; the terms are the shard's own.
 */
export function JoinFlow({ entry, suggestedPlace, onJoined, onClose, arrival }: Props) {
  const [mode, setMode] = useState<Mode>(arrival || getPlayer() ? "login" : "register");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [identifier, setIdentifier] = useState(getPlayer()?.email ?? "");
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [resetNotice, setResetNotice] = useState("");
  const [verificationToken, setVerificationToken] = useState("");
  const [verificationNotice, setVerificationNotice] = useState("");
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
    const params = new URLSearchParams(window.location.search);
    const verification = params.get("verify_token");
    if (verification) {
      setVerificationToken(verification);
      setMode("verify");
      return;
    }
    const reset = params.get("reset_token");
    if (reset) {
      setResetToken(reset);
      setMode("reset");
    }
  }, []);

  useEffect(() => {
    if (place) return;
    if (suggestedPlace && entryPlaces.includes(suggestedPlace)) {
      setPlace(suggestedPlace);
    } else if (entryPlaces.length > 0) {
      setPlace(entryPlaces[0]);
    }
  }, [suggestedPlace, entryPlaces, place]);

  function rememberAuth(auth: AuthResponse) {
    setJwt(auth.token);
    setPlayer({
      actor_id: auth.actor_id,
      player_id: auth.player_id,
      username: auth.username,
      email: auth.email,
      display_name: auth.display_name,
    });
  }

  async function finishEntry(auth: AuthResponse) {
    rememberAuth(auth);
    if (arrival) {
      await arrival.onAuthenticated();
      return;
    }
    const existing = await getCurrentSession();
    if (existing.active) {
      if (!existing.session_id || !existing.location) {
        throw new Error("Your existing town session could not be recovered safely.");
      }
      setSessionId(existing.session_id);
      setStandingPlace(existing.location);
      onJoined(existing.location, auth.display_name);
      return;
    }
    const sessionId = mintSessionId();
    try {
      await postSessionBootstrap(sessionId, entry!.world_id, auth.display_name, place!);
    } catch (cause) {
      // Another browser may have entered after the check above. Recover only
      // the session authenticated as this same actor; never adopt an ID from
      // an error message.
      if (!(cause instanceof ApiError) || cause.status !== 409) throw cause;
      const raced = await getCurrentSession();
      if (!raced.active || !raced.session_id || !raced.location) throw cause;
      setSessionId(raced.session_id);
      setStandingPlace(raced.location);
      onJoined(raced.location, auth.display_name);
      return;
    }
    setStandingPlace(place!);
    onJoined(place!, auth.display_name);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || (!arrival && (!entry || !place))) return;
    setBusy(true);
    setError("");
    try {
      const auth = mode === "register" && !arrival
        ? await postRegister({ email, password, password_confirmation: passwordConfirmation, terms_accepted: termsAccepted })
        : mode === "verify"
          ? await postVerifyEmail(verificationToken)
        : mode === "profile"
          ? await patchProfile(displayName)
          : mode === "reset"
            ? await postResetPassword(resetToken, newPassword)
            : await postLogin(identifier, password);
      rememberAuth(auth);
      if (auth.email_verification_required && !auth.email_verified) {
        setVerificationNotice("Check your email for a one-time verification link or token.");
        setMode("verify");
        return;
      }
      if (mode === "verify") {
        const url = new URL(window.location.href);
        url.searchParams.delete("verify_token");
        window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
      }
      if (!auth.profile_complete) {
        setDisplayName("");
        setMode("profile");
        return;
      }
      await finishEntry(auth);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "That didn't work — try again.");
    } finally {
      setBusy(false);
    }
  }

  const registerReady = email && password.length >= 8 && password === passwordConfirmation && termsText && termsAccepted && !termsLoading && !termsError;
  const profileReady = displayName.trim().length > 0;
  const verificationReady = verificationToken.trim().length >= 12;
  const loginReady = identifier && password;
  const resetReady = resetToken && newPassword.length >= 8;

  async function requestReset() {
    if (busy || !identifier.trim()) return;
    setBusy(true);
    setError("");
    setResetNotice("");
    try {
      await postRequestPasswordReset(identifier.trim());
      setResetNotice("If that account exists, a one-time reset token has been emailed. It expires in 30 minutes.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The reset request could not be sent.");
    } finally {
      setBusy(false);
    }
  }

  async function resendVerification() {
    if (busy) return;
    setBusy(true);
    setError("");
    setVerificationNotice("");
    try {
      const result = await postResendVerification();
      setVerificationNotice(
        result.already_verified
          ? "This email is already verified. Sign in again to continue."
          : result.retry_later
            ? "A verification email was sent recently. Please wait a minute before asking again."
            : result.sent
              ? "A fresh verification link has been sent."
              : "No new verification email was needed.",
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The verification email could not be sent.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="threshold">
      <div className="threshold-card join-card" role="dialog" aria-labelledby="join-title">
        <h1 id="join-title" className="threshold-title">{mode === "verify" ? "Verify your email" : mode === "profile" ? "Choose your public name" : arrival ? "Sign in to finish your trip" : "Join the world"}</h1>
        {mode !== "profile" && mode !== "verify" && <div className="join-tabs" aria-label="Choose how to join">
          {!arrival && (
            <button type="button" aria-pressed={mode === "register"} className={mode === "register" ? "is-active" : ""} onClick={() => setMode("register")}>
              New here
            </button>
          )}
          <button type="button" aria-pressed={mode === "login"} className={mode === "login" ? "is-active" : ""} onClick={() => setMode("login")}>
            Coming back
          </button>
          <button type="button" aria-pressed={mode === "reset"} className={mode === "reset" ? "is-active" : ""} onClick={() => setMode("reset")}>
            Reset password
          </button>
        </div>}

        <form onSubmit={submit} className="join-form">
          {mode === "register" ? (
            <>
              <label className="sr-only" htmlFor="join-email">Email</label>
              <input id="join-email" type="email" placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
              <label className="sr-only" htmlFor="join-new-password">Password, at least 8 characters</label>
              <input id="join-new-password" type="password" placeholder="password (8+ characters)" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
              <label className="sr-only" htmlFor="join-confirm-password">Confirm password</label>
              <input id="join-confirm-password" type="password" placeholder="confirm password" value={passwordConfirmation} onChange={(e) => setPasswordConfirmation(e.target.value)} autoComplete="new-password" />
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
          ) : mode === "verify" ? (
            <>
              <p className="place-empty">Use the one-time token from your verification email. You can also open the link in that email.</p>
              <label className="sr-only" htmlFor="verification-token">Email verification token</label>
              <input id="verification-token" placeholder="verification token" value={verificationToken} onChange={(e) => setVerificationToken(e.target.value)} autoComplete="one-time-code" autoFocus />
              <button type="button" className="btn btn-quiet reset-request" disabled={busy} onClick={() => void resendVerification()}>
                Send another verification email
              </button>
              {verificationNotice && <p className="object-notice" role="status">{verificationNotice}</p>}
            </>
          ) : mode === "profile" ? (
            <>
              <p className="place-empty">This is the name people and residents will see. You can change it later from your account.</p>
              <label className="sr-only" htmlFor="join-display-name">Name people will see</label>
              <input id="join-display-name" placeholder="name people will see" value={displayName} onChange={(e) => setDisplayName(e.target.value)} autoFocus />
            </>
          ) : mode === "login" ? (
            <>
              <label className="sr-only" htmlFor="join-identifier">Email</label>
              <input id="join-identifier" type="email" placeholder="email" value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoComplete="email" />
              <label className="sr-only" htmlFor="join-password">Password</label>
              <input id="join-password" type="password" placeholder="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            </>
          ) : (
            <>
              <label className="sr-only" htmlFor="reset-identifier">Email</label>
              <input id="reset-identifier" type="email" placeholder="email" value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoComplete="email" />
              <button type="button" className="btn btn-quiet reset-request" disabled={busy || !identifier.trim()} onClick={() => void requestReset()}>
                Email a reset token
              </button>
              {resetNotice && <p className="object-notice" role="status">{resetNotice}</p>}
              <label className="sr-only" htmlFor="reset-token">One-time reset token</label>
              <input id="reset-token" placeholder="one-time reset token" value={resetToken} onChange={(e) => setResetToken(e.target.value)} autoComplete="off" />
              <label className="sr-only" htmlFor="reset-new-password">New password, at least 8 characters</label>
              <input id="reset-new-password" type="password" placeholder="new password (8+ characters)" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} autoComplete="new-password" />
            </>
          )}

          {!arrival && entryPlaces.length > 0 && (
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
            <button type="submit" className="btn btn-primary" disabled={busy || (!arrival && !place) || !(mode === "register" ? registerReady : mode === "verify" ? verificationReady : mode === "profile" ? profileReady : mode === "reset" ? resetReady : loginReady)}>
              {busy ? "Checking…" : mode === "verify" ? "Verify email" : mode === "profile" ? "Use this name and enter" : arrival ? (mode === "reset" ? "Reset and finish the trip" : "Sign in and finish the trip") : mode === "reset" ? "Reset and step into the world" : mode === "register" ? "Create account" : "Step into the world"}
            </button>
            <button type="button" className="btn btn-quiet" onClick={onClose}>
              {arrival ? "Return to the map" : "Just look around instead"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
