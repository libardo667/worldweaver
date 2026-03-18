import { useEffect, useState } from "react";
import { postDM, type DMRecipient } from "../api/wwClient";

type LetterComposeProps = {
  defaultFromName?: string;
  sessionId?: string;
  availableRecipients?: DMRecipient[];
  onSent?: (sent: { recipientKey: string; recipientLabel: string; body: string; dmId: number }) => void;
  preferredRecipient?: string;
};

export function LetterCompose({ defaultFromName = "", sessionId, availableRecipients = [], onSent, preferredRecipient }: LetterComposeProps) {
  const [open, setOpen] = useState(false);
  const [recipientKey, setRecipientKey] = useState(availableRecipients[0]?.key ?? "");
  useEffect(() => {
    if (availableRecipients.length > 0 && !availableRecipients.some((item) => item.key === recipientKey)) {
      setRecipientKey(availableRecipients[0].key);
    }
  }, [availableRecipients, recipientKey]);
  useEffect(() => {
    if (preferredRecipient && availableRecipients.some((item) => item.key === preferredRecipient) && preferredRecipient !== recipientKey) {
      setRecipientKey(preferredRecipient);
    }
  }, [availableRecipients, preferredRecipient, recipientKey]);
  const [fromName, setFromName] = useState(defaultFromName);
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectedRecipient = availableRecipients.find((item) => item.key === recipientKey) ?? null;

  async function handleSend() {
    if (!fromName.trim() || !body.trim() || sending || !selectedRecipient) return;
    setSending(true);
    setError(null);
    try {
      const result = await postDM(selectedRecipient, fromName.trim(), body.trim(), sessionId);
      setSent(true);
      const sentBody = body.trim();
      setBody("");
      onSent?.({
        recipientKey: selectedRecipient.key,
        recipientLabel: selectedRecipient.label,
        body: sentBody,
        dmId: result.dm_id,
      });
      setTimeout(() => setSent(false), 3000);
    } catch (err) {
      setError(String(err));
    } finally {
      setSending(false);
    }
  }

  if (!open) {
    return (
      <button className="ww-letter-toggle" onClick={() => setOpen(true)} disabled={availableRecipients.length === 0} title={availableRecipients.length === 0 ? "Meet someone first" : undefined}>
        ✉ Send a letter
      </button>
    );
  }

  if (availableRecipients.length === 0) {
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
          value={recipientKey}
          onChange={(e) => setRecipientKey(e.target.value)}
          disabled={sending}
        >
          {availableRecipients.map((recipient) => (
            <option key={recipient.key} value={recipient.key}>
              {recipient.label} {recipient.recipient_type === "player" ? "· player" : "· resident"}
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
        <p className="ww-letter-sent">Letter sent to {selectedRecipient?.label ?? "them"}.</p>
      ) : (
        <button
          className="ww-letter-send"
          onClick={() => void handleSend()}
          disabled={sending || !fromName.trim() || !body.trim() || !selectedRecipient}
        >
          {sending ? "Sending…" : "Send →"}
        </button>
      )}
    </div>
  );
}
