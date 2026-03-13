import { useEffect, useState } from "react";
import { postLetter } from "../api/wwClient";

type LetterComposeProps = {
  defaultFromName?: string;
  sessionId?: string;
  availableAgents?: string[];
};

export function LetterCompose({ defaultFromName = "", sessionId, availableAgents = [] }: LetterComposeProps) {
  const [open, setOpen] = useState(false);
  const [toAgent, setToAgent] = useState(availableAgents[0] ?? "");
  useEffect(() => {
    if (availableAgents.length > 0 && !availableAgents.includes(toAgent)) {
      setToAgent(availableAgents[0]);
    }
  }, [availableAgents, toAgent]);
  const [fromName, setFromName] = useState(defaultFromName);
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend() {
    if (!fromName.trim() || !body.trim() || sending) return;
    setSending(true);
    setError(null);
    try {
      await postLetter(toAgent, fromName.trim(), body.trim(), sessionId);
      setSent(true);
      setBody("");
      setTimeout(() => setSent(false), 3000);
    } catch (err) {
      setError(String(err));
    } finally {
      setSending(false);
    }
  }

  if (!open) {
    return (
      <button className="ww-letter-toggle" onClick={() => setOpen(true)} disabled={availableAgents.length === 0} title={availableAgents.length === 0 ? "Meet someone first" : undefined}>
        ✉ Send a letter
      </button>
    );
  }

  if (availableAgents.length === 0) {
    return (
      <div className="ww-letter-compose">
        <div className="ww-letter-compose-header">
          <span>✉ Letter</span>
          <button className="ww-icon-btn" onClick={() => setOpen(false)}>✕</button>
        </div>
        <p className="ww-letter-no-contacts">No contacts yet. Meet someone first.</p>
      </div>
    );
  }

  return (
    <div className="ww-letter-compose">
      <div className="ww-letter-compose-header">
        <span>✉ Letter</span>
        <button className="ww-icon-btn" onClick={() => { setOpen(false); setError(null); }}>✕</button>
      </div>

      <div className="ww-letter-field">
        <label className="ww-letter-label">To</label>
        <select
          className="ww-letter-select"
          value={toAgent}
          onChange={(e) => setToAgent(e.target.value)}
          disabled={sending}
        >
          {availableAgents.map((a) => (
            <option key={a} value={a}>
              {a.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
            </option>
          ))}
        </select>
      </div>

      <div className="ww-letter-field">
        <label className="ww-letter-label">From</label>
        <input
          className="ww-letter-input"
          placeholder="Your name"
          value={fromName}
          onChange={(e) => setFromName(e.target.value)}
          disabled={sending}
        />
      </div>

      <textarea
        className="ww-letter-body"
        placeholder="Write your letter…"
        rows={5}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        disabled={sending}
      />

      {error && <p className="ww-letter-error">{error}</p>}

      {sent ? (
        <p className="ww-letter-sent">Letter delivered. They'll find it soon.</p>
      ) : (
        <button
          className="ww-letter-send"
          onClick={() => void handleSend()}
          disabled={sending || !fromName.trim() || !body.trim()}
        >
          {sending ? "Sending…" : "Send →"}
        </button>
      )}
    </div>
  );
}
