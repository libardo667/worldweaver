// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useEffect, useState } from "react";
import { browseStoopAt, postTakeStoopEntry } from "../api/ww";
import type { StoopBrowse, StoopShell } from "../api/types";
import { usePoll } from "../hooks/usePoll";

type Props = {
  location: string;
  stoops: StoopShell[];
  /** Session of a participant standing at this exact place; enables taking. */
  takerSessionId?: string | null;
  /** Bumped by the parent when the world changed elsewhere in the panel. */
  refreshKey?: number;
  /** Called after taking so sibling views (carried objects) can refresh. */
  onTook?: () => void;
};

/**
 * Things people left for whoever comes next. Browsing is an explicit act —
 * a stoop announces itself but never spills its contents into the view.
 */
export function StoopHere({ location, stoops, takerSessionId, refreshKey = 0, onTook }: Props) {
  const [openStoopId, setOpenStoopId] = useState<string | null>(null);
  const [browse, setBrowse] = useState<StoopBrowse | null>(null);
  const [refreshCount, setRefreshCount] = useState(0);
  const [takingEntryId, setTakingEntryId] = useState<string | null>(null);

  useEffect(() => {
    setOpenStoopId(null);
    setBrowse(null);
  }, [location]);

  useEffect(() => {
    if (!openStoopId) {
      setBrowse(null);
      return;
    }
    let live = true;
    browseStoopAt(openStoopId, location)
      .then((result) => {
        if (live) setBrowse(result);
      })
      .catch(() => {
        if (live) setBrowse(null);
      });
    return () => {
      live = false;
    };
  }, [openStoopId, location, refreshCount, refreshKey]);

  // An opened stoop is being watched: refetch its entries so someone else's
  // leave/take shows up without reopening.
  usePoll(async () => {
    setRefreshCount((n) => n + 1);
  }, openStoopId ? 10_000 : null);

  async function takeEntry(entryId: string) {
    if (!takerSessionId || takingEntryId) return;
    setTakingEntryId(entryId);
    try {
      await postTakeStoopEntry(entryId, takerSessionId);
      setRefreshCount((n) => n + 1);
      onTook?.();
    } catch {
      // The entry may have just been taken by someone else; refresh shows truth.
      setRefreshCount((n) => n + 1);
    } finally {
      setTakingEntryId(null);
    }
  }

  if (stoops.length === 0) return null;

  return (
    <section className="place-section">
      <h3 className="place-section-title">On the stoop</h3>
      {stoops.map((stoop) => (
        <div key={stoop.stoop_id} className="stoop">
          <button
            className="stoop-shell"
            onClick={() => setOpenStoopId(openStoopId === stoop.stoop_id ? null : stoop.stoop_id)}
            aria-expanded={openStoopId === stoop.stoop_id}
          >
            <span className="stoop-title">{stoop.title}</span>
            <span className="stoop-count">
              {stoop.active_count === 0 ? "empty" : `${stoop.active_count} thing${stoop.active_count === 1 ? "" : "s"} left`}
            </span>
          </button>
          {openStoopId === stoop.stoop_id && (
            <div className="stoop-entries">
              {stoop.prompt && <p className="stoop-prompt">{stoop.prompt}</p>}
              {browse == null ? (
                <p className="place-empty">Looking…</p>
              ) : browse.entries.length === 0 ? (
                <p className="place-empty">Nothing here right now — space for {stoop.space_remaining}.</p>
              ) : (
                browse.entries.map((entry) => (
                  <div key={entry.entry_id} className="stoop-entry">
                    <span className="stoop-entry-name">{entry.object.name}</span>
                    {entry.object.description && <span className="stoop-entry-desc">{entry.object.description}</span>}
                    {takerSessionId && (
                      <button className="stoop-take" onClick={() => takeEntry(entry.entry_id)} disabled={takingEntryId != null}>
                        {takingEntryId === entry.entry_id ? "Taking…" : "Take it with you"}
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      ))}
    </section>
  );
}
