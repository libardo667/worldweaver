// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useState } from "react";
import type { FormEvent } from "react";
import { postSpeak } from "../api/ww";

type Props = {
  location: string;
  sessionId: string;
  displayName: string;
  onSpoke: () => void;
};

/** Say something at the place you are actually standing. */
export function SpeakBar({ location, sessionId, displayName, onSpoke }: Props) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const text = message.trim();
    if (!text || busy) return;
    setBusy(true);
    try {
      await postSpeak(location, sessionId, displayName, text);
      setMessage("");
      onSpoke();
    } catch {
      // Leave the text in the box so nothing said is lost.
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="speak-bar" onSubmit={submit}>
      <input
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder={`Say something here, as ${displayName}`}
        maxLength={500}
      />
      <button type="submit" className="btn btn-primary speak-send" disabled={busy || !message.trim()}>
        Say
      </button>
    </form>
  );
}
