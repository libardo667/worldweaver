// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { FormEvent, useCallback, useEffect, useState } from "react";
import { getWorldTraces, postWorldTrace } from "../api/ww";
import type { WorldTrace } from "../api/types";
import { usePoll } from "../hooks/usePoll";

type Props = {
  location: string;
  sessionId: string;
};

/** Public, expiring physical marks at the participant's exact current place. */
export function MarksHere({ location, sessionId }: Props) {
  const [traces, setTraces] = useState<WorldTrace[]>([]);
  const [body, setBody] = useState("");
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    const result = await getWorldTraces(sessionId);
    setTraces(result.traces ?? []);
  }, [sessionId]);

  useEffect(() => {
    void refresh().catch(() => setTraces([]));
  }, [location, refresh]);

  usePoll(refresh, 10_000);

  async function leaveMark(event: FormEvent) {
    event.preventDefault();
    const cleanBody = body.trim();
    if (!cleanBody || busy) return;
    setBusy(true);
    setNotice("");
    setError("");
    try {
      await postWorldTrace(sessionId, cleanBody, target.trim());
      setBody("");
      setTarget("");
      setNotice("Your mark is here for later visitors.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The mark could not be left.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="place-section marks-here">
      <h3 className="place-section-title">Marks here</h3>
      {traces.length === 0 ? (
        <p className="stoop-entry-desc">No one else has left a mark here.</p>
      ) : (
        <div className="mark-list">
          {traces.map((trace) => (
            <div className="mark-entry" key={trace.trace_id}>
              <span className="stoop-entry-name">{trace.author_name || "Someone"}</span>
              <span className="stoop-entry-desc">
                {trace.target ? `On ${trace.target}: ` : ""}{trace.body}
              </span>
            </div>
          ))}
        </div>
      )}

      <details className="mark-form">
        <summary>Leave a mark</summary>
        <p className="stoop-entry-desc">A mark stays at this exact place for later visitors. It is not speech.</p>
        <form onSubmit={(event) => void leaveMark(event)}>
          <label htmlFor="mark-target">Surface or object (optional)</label>
          <input
            id="mark-target"
            value={target}
            maxLength={200}
            onChange={(event) => setTarget(event.target.value)}
            placeholder="the gatepost"
          />
          <label htmlFor="mark-body">What remains here</label>
          <textarea
            id="mark-body"
            value={body}
            maxLength={500}
            required
            onChange={(event) => setBody(event.target.value)}
            placeholder="three chalk lines"
          />
          <button className="stoop-take" type="submit" disabled={busy || !body.trim()}>
            {busy ? "Leaving it…" : "Leave this mark"}
          </button>
        </form>
      </details>

      {notice && <p className="object-notice" role="status">{notice}</p>}
      {error && <p className="object-error" role="alert">{error}</p>}
    </section>
  );
}
