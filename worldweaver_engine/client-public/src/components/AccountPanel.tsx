// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useState } from "react";
import type { FormEvent } from "react";
import { patchProfile } from "../api/ww";
import { setJwt, setPlayer } from "../session/store";

type Props = {
  displayName: string;
  place: string;
  onUpdated: (displayName: string) => void;
  onClose: () => void;
};

/** Small account surface for correcting the public name without changing identity. */
export function AccountPanel({ displayName, place, onUpdated, onClose }: Props) {
  const [name, setName] = useState(displayName);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    const cleaned = name.trim();
    if (!cleaned || busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const auth = await patchProfile(cleaned);
      setJwt(auth.token);
      setPlayer({
        actor_id: auth.actor_id,
        player_id: auth.player_id,
        username: auth.username,
        display_name: auth.display_name,
      });
      setName(auth.display_name);
      onUpdated(auth.display_name);
      setNotice("Your public name has been updated.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Your public name could not be updated.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="threshold">
      <div className="threshold-card" role="dialog" aria-labelledby="account-title">
        <h1 id="account-title" className="threshold-title">Your account</h1>
        <p className="threshold-summary">You are standing at {place}. Your public name is shown to people and residents you encounter.</p>
        <form className="join-form" onSubmit={submit}>
          <label htmlFor="account-display-name">Public name</label>
          <input
            id="account-display-name"
            value={name}
            maxLength={120}
            onChange={(event) => setName(event.target.value)}
            autoComplete="name"
          />
          {error && <p className="join-error" role="alert">{error}</p>}
          {notice && <p className="object-notice" role="status">{notice}</p>}
          <div className="threshold-actions">
            <button type="submit" className="btn btn-primary" disabled={busy || !name.trim() || name.trim() === displayName}>
              {busy ? "Saving…" : "Save public name"}
            </button>
            <button type="button" className="btn btn-quiet" onClick={onClose}>Back to the world</button>
          </div>
        </form>
      </div>
    </div>
  );
}
