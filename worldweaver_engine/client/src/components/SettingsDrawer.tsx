import { useState, useEffect } from "react";
import type { ModelSummary, CurrentModelResponse } from "../types";
import {
  getAvailableModels,
  getCurrentModel,
  postSettingsKey,
  putCurrentModel,
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
  onModelChanged?: (model: CurrentModelResponse) => void;
};

type Tab = "narrative" | "tethered";

export function SettingsDrawer({ isOpen, onClose, onModelChanged }: SettingsDrawerProps) {
  const [tab, setTab] = useState<Tab>("narrative");

  // Narrative Key tab state
  const [apiKey, setApiKey] = useState("");
  const [currentModel, setCurrentModel] = useState<CurrentModelResponse | null>(null);
  const [availableModels, setAvailableModels] = useState<ModelSummary[]>([]);
  const [keyPending, setKeyPending] = useState(false);
  const [modelPending, setModelPending] = useState(false);
  const [keyMessage, setKeyMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  // Tethered Mode tab state
  const playerInfo = getPlayerInfo();
  const [displayName, setDisplayName] = useState(playerInfo?.display_name ?? "");
  const [pronouns, setPronouns] = useState("");
  const [description, setDescription] = useState("");
  const [nonNegotiables, setNonNegotiables] = useState("");
  const [shadowConsent, setShadowConsent] = useState(false);
  const [identityPending, setIdentityPending] = useState(false);
  const [identityMessage, setIdentityMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  useEffect(() => {
    if (isOpen) {
      refreshModelData();
    }
  }, [isOpen]);

  async function refreshModelData() {
    try {
      const [models, active] = await Promise.all([getAvailableModels(), getCurrentModel()]);
      setAvailableModels(models);
      setCurrentModel(active);
    } catch (err) {
      console.error("Failed to refresh model data", err);
    }
  }

  async function handleKeyUpdate(e: React.FormEvent) {
    e.preventDefault();
    if (!apiKey.trim()) return;
    setKeyPending(true);
    setKeyMessage(null);
    try {
      await postSettingsKey(apiKey);
      setApiKey("");
      setKeyMessage({ text: "API key updated.", type: "success" });
      refreshModelData();
    } catch (err) {
      setKeyMessage({ text: err instanceof Error ? err.message : "Failed to update key.", type: "error" });
    } finally {
      setKeyPending(false);
    }
  }

  async function handleModelChange(modelId: string) {
    if (modelId === currentModel?.model_id) return;
    setModelPending(true);
    setKeyMessage(null);
    try {
      await putCurrentModel(modelId);
      const refreshed = await getCurrentModel();
      setCurrentModel(refreshed);
      if (onModelChanged) onModelChanged(refreshed);
      setKeyMessage({ text: `Switched to ${refreshed.label}.`, type: "success" });
    } catch (err) {
      setKeyMessage({ text: err instanceof Error ? err.message : "Failed to switch model.", type: "error" });
    } finally {
      setModelPending(false);
    }
  }

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

  function handleLogout() {
    clearSessionStorage();
    clearJwt();
    window.location.reload();
  }

  if (!isOpen) return null;

  const isPending = keyPending || modelPending;

  return (
    <div className="modal-overlay settings-drawer-overlay" onClick={onClose}>
      <div className="panel settings-drawer" onClick={(e) => e.stopPropagation()} role="dialog">
        <header className="panel-header">
          <h2>Settings</h2>
          <button className="close-btn" onClick={onClose} aria-label="Close settings">×</button>
        </header>

        <nav className="settings-tabs">
          <button
            className={`settings-tab-btn${tab === "narrative" ? " active" : ""}`}
            onClick={() => setTab("narrative")}
          >
            Narrative Key
          </button>
          <button
            className={`settings-tab-btn${tab === "tethered" ? " active" : ""}`}
            onClick={() => setTab("tethered")}
          >
            Tethered Mode
          </button>
        </nav>

        {tab === "narrative" && (
          <div className="settings-tab-content">
            <section className="settings-section">
              <h3>Narrator Access</h3>
              <div className="settings-demo-notice">
                <strong>Demo period:</strong> narration is covered through <strong>March 23, 2026</strong>.
                After that date, you&apos;ll need your own <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer">OpenRouter API key</a> to
                keep acting in the world. Without one, your character will shift into observer mode — still
                present, still remembered, just quiet — until a key is provided.
              </div>
              <details className="settings-disclosure">
                <summary>What does my key pay for?</summary>
                <p>
                  Only the <strong>narrator</strong> — the model that turns your actions into prose.
                  A separate fixed model handles world logic and story consistency; you won&apos;t pay for that.
                  One narrative turn costs roughly the same as reading a short paragraph.
                </p>
              </details>
              <details className="settings-disclosure">
                <summary>How is my key stored?</summary>
                <p>
                  Stored server-side, encrypted at rest. Never logged, never shared. Transmitted only to
                  OpenRouter for your narrative requests. You can revoke it from your OpenRouter dashboard
                  at any time — narration stops immediately.
                </p>
              </details>
              <details className="settings-disclosure">
                <summary>What happens when the demo ends?</summary>
                <p>
                  On March 23, you&apos;ll see a notice in-app on your next action turn. Your character
                  stays in the world in observer mode. Add a key here to resume. No email, no pressure —
                  the world just waits.
                </p>
              </details>
              <p className="settings-blurb muted" style={{ marginTop: "1rem", fontStyle: "italic" }}>
                Your key is tied to your federation identity and follows you across cities.
              </p>
              <form onSubmit={handleKeyUpdate} className="settings-key-form">
                <input
                  type="password"
                  value={apiKey}
                  placeholder="sk-or-v1-..."
                  onChange={(e) => setApiKey(e.target.value)}
                  disabled={keyPending}
                  autoComplete="off"
                />
                <button type="submit" className="choice-btn" disabled={keyPending || !apiKey.trim()}>
                  {keyPending ? "Saving..." : "Save Key"}
                </button>
              </form>
            </section>

            <section className="settings-section">
              <h3>Narrative Voice</h3>
              <p className="settings-blurb muted">
                Choose the style of narrator that renders your story. This affects prose quality, speed,
                and cost — nothing else. World logic, what&apos;s plausible, and story consistency are
                handled by a separate fixed model this setting doesn&apos;t touch.
              </p>
              <select
                value={currentModel?.model_id || ""}
                onChange={(e) => handleModelChange(e.target.value)}
                disabled={isPending}
              >
                {availableModels.map((m) => (
                  <option key={m.model_id} value={m.model_id}>
                    {m.label} — {m.tier}
                  </option>
                ))}
              </select>
              {currentModel && (
                <div className="model-details muted">
                  <p>Narrative quality: {currentModel.creative_quality}/10</p>
                  <p>Est. cost per 10 turns (once billing is live): ${currentModel.estimated_session_cost.total_cost_usd.toFixed(2)}</p>
                </div>
              )}
            </section>

            {keyMessage && (
              <p className={keyMessage.type === "success" ? "success-text" : "error-text"}>
                {keyMessage.text}
              </p>
            )}
          </div>
        )}

        {tab === "tethered" && (
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
        )}

        <footer className="settings-footer">
          {playerInfo && (
            <p className="muted small" style={{ marginBottom: "0.75rem" }}>
              Signed in as <strong>{playerInfo.display_name || playerInfo.username}</strong>
            </p>
          )}
          <button className="settings-logout-btn" onClick={handleLogout}>
            Leave the world
          </button>
          <p className="muted small" style={{ marginTop: "0.5rem" }}>
            Clears your session. Your character&apos;s story remains in the world.
          </p>
        </footer>
      </div>
    </div>
  );
}
