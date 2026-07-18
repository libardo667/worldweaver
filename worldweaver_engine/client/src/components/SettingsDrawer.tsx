// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useState } from "react";
import {
  postLeaveSession,
  postShadowConsent,
} from "../api/wwClient";
import {
  getPlayerInfo,
  getOrCreateSessionId,
  clearSessionStorage,
  clearJwt,
} from "../state/sessionStore";

type SettingsDrawerProps = {
  isOpen: boolean;
  onClose: () => void;
  sessionId: string;
};

export function SettingsDrawer({ isOpen, onClose, sessionId }: SettingsDrawerProps) {
  const playerInfo = getPlayerInfo();
  const [displayName, setDisplayName] = useState(playerInfo?.display_name ?? "");
  const [pronouns, setPronouns] = useState("");
  const [description, setDescription] = useState("");
  const [nonNegotiables, setNonNegotiables] = useState("");
  const [shadowConsent, setShadowConsent] = useState(false);
  const [identityPending, setIdentityPending] = useState(false);
  const [identityMessage, setIdentityMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);
  const [logoutPending, setLogoutPending] = useState(false);
  const [logoutMessage, setLogoutMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  async function handleIdentitySave(e: React.FormEvent) {
    e.preventDefault();
    setIdentityPending(true);
    setIdentityMessage(null);
    try {
      const sessionId = getOrCreateSessionId();
      const lines = nonNegotiables
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean);
      await postShadowConsent({ session_id: sessionId, consent: shadowConsent, non_negotiables: lines });
      setIdentityMessage({ text: "Identity saved. Your tether is recorded.", type: "success" });
    } catch (err) {
      setIdentityMessage({ text: err instanceof Error ? err.message : "Failed to save identity.", type: "error" });
    } finally {
      setIdentityPending(false);
    }
  }

  async function handleLogout() {
    setLogoutPending(true);
    setLogoutMessage(null);
    try {
      await postLeaveSession(sessionId);
      clearSessionStorage();
      clearJwt();
      window.location.reload();
    } catch (err) {
      setLogoutMessage({
        text: err instanceof Error ? err.message : "Failed to leave the world cleanly.",
        type: "error",
      });
    } finally {
      setLogoutPending(false);
    }
  }

  if (!isOpen) return null;

  return (
    <div className="modal-overlay settings-drawer-overlay" onClick={onClose}>
      <div className="panel settings-drawer" onClick={(e) => e.stopPropagation()} role="dialog">
        <header className="panel-header">
          <h2>Settings</h2>
          <button className="close-btn" onClick={onClose} aria-label="Close settings">×</button>
        </header>

        <div className="settings-tab-content">
            <section className="settings-section">
              <h3>What is Tethered Mode?</h3>
              <p className="settings-blurb muted">
                When you step away, your character doesn&apos;t disappear — they continue as an AI shadow,
                keeping your place in the story. Other characters will still encounter you. The narrative
                moves around your absence rather than ignoring it.
              </p>
              <p className="settings-blurb muted">
                Disabling tethered mode doesn&apos;t remove you from the narrative immediately — that
                would be like dying. Your shadow fades naturally over time, and you can return whenever
                you&apos;re ready.
              </p>
            </section>

            <section className="settings-section">
              <h3>Privacy &amp; Data</h3>
              <p className="settings-blurb muted">
                WorldWeaver records events, movements, and chat as part of the shared world&apos;s memory.
                Your identity form below is used to make your shadow a faithful representation of you —
                it informs how your character speaks and what they care about. None of this is sold.
                It exists for storytelling and to contribute to the narrative zeitgeist of the world.
              </p>
              <p className="settings-blurb muted">
                If you choose to enable your shadow, you can review the soul notes your shadow accumulates
                when you return. Anything that drifted too far from who you are can be pruned. Real-life
                events you want woven in can be added.
              </p>
            </section>

            <section className="settings-section">
              <h3>Identity Form</h3>
              <form onSubmit={handleIdentitySave} className="settings-identity-form">
                <label className="settings-label">
                  Display Name
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="How you appear to others"
                    disabled={identityPending}
                  />
                </label>

                <label className="settings-label">
                  Pronouns
                  <input
                    type="text"
                    value={pronouns}
                    onChange={(e) => setPronouns(e.target.value)}
                    placeholder="e.g. he/him, she/her, they/them"
                    disabled={identityPending}
                  />
                </label>

                <label className="settings-label">
                  Who are you?
                  <span className="settings-label-hint muted">
                    A few sentences your shadow will inhabit. Speak in first person or third — whatever
                    feels right. This is your narrative anchor.
                  </span>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="I move through the city like... / They grew up in the..."
                    rows={5}
                    disabled={identityPending}
                  />
                </label>

                <label className="settings-label">
                  Non-negotiables
                  <span className="settings-label-hint muted">
                    Things your shadow should never do or say — one per line. These are hard constraints
                    the narrative engine will respect.
                  </span>
                  <textarea
                    value={nonNegotiables}
                    onChange={(e) => setNonNegotiables(e.target.value)}
                    placeholder={"Never claims to be human when sincerely asked\nNever reveals my real name"}
                    rows={3}
                    disabled={identityPending}
                  />
                </label>

                <label className="settings-consent-row">
                  <input
                    type="checkbox"
                    checked={shadowConsent}
                    onChange={(e) => setShadowConsent(e.target.checked)}
                    disabled={identityPending}
                  />
                  <span>
                    Enable tethered mode — I consent to an AI shadow representing me when I&apos;m absent
                  </span>
                </label>

                {!shadowConsent && (
                  <p className="muted settings-blurb" style={{ fontSize: "0.8rem" }}>
                    Shadow disabled. You can enable it at any time. Your character will simply be absent
                    when you&apos;re not actively present.
                  </p>
                )}

                <button type="submit" className="choice-btn" disabled={identityPending}>
                  {identityPending ? "Saving…" : "Save Identity"}
                </button>

                {identityMessage && (
                  <p className={identityMessage.type === "success" ? "success-text" : "error-text"}>
                    {identityMessage.text}
                  </p>
                )}
              </form>
            </section>
        </div>

        <footer className="settings-footer">
          {playerInfo && (
            <p className="muted small" style={{ marginBottom: "0.75rem" }}>
              Signed in as <strong>{playerInfo.display_name || playerInfo.username}</strong>
            </p>
          )}
          <button className="settings-logout-btn" onClick={() => void handleLogout()} disabled={logoutPending}>
            {logoutPending ? "Leaving..." : "Leave the world"}
          </button>
          {logoutMessage && (
            <p className={logoutMessage.type === "success" ? "success-text" : "error-text"} style={{ marginTop: "0.5rem" }}>
              {logoutMessage.text}
            </p>
          )}
          <p className="muted small" style={{ marginTop: "0.5rem" }}>
            Clears your session. Your character&apos;s story remains in the world.
          </p>
        </footer>
      </div>
    </div>
  );
}
