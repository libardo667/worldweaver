// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useEffect, useState } from "react";
import { browseStoopAt } from "../api/ww";
import type { StoopBrowse, StoopShell } from "../api/types";

/**
 * Things people left for whoever comes next. Browsing is an explicit act —
 * a stoop announces itself but never spills its contents into the view.
 */
export function StoopHere({ location, stoops }: { location: string; stoops: StoopShell[] }) {
  const [openStoopId, setOpenStoopId] = useState<string | null>(null);
  const [browse, setBrowse] = useState<StoopBrowse | null>(null);

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
  }, [openStoopId, location]);

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
