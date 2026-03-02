import { useEffect, useMemo, useState } from "react";
import type { ChangeItem } from "../types";
import {
  loadWhatChangedCollapsed,
  saveWhatChangedCollapsed,
} from "../state/sessionStore";
import { DEFAULT_RECEIPT_LIMIT } from "../utils/diffVars";

type WhatChangedStripProps = {
  changes: ChangeItem[];
};

export function WhatChangedStrip({ changes }: WhatChangedStripProps) {
  const [collapsed, setCollapsed] = useState<boolean>(() => loadWhatChangedCollapsed());
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    setExpanded(false);
  }, [changes]);

  const visibleChanges = useMemo(() => {
    if (expanded) {
      return changes;
    }
    return changes.slice(0, DEFAULT_RECEIPT_LIMIT);
  }, [changes, expanded]);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      saveWhatChangedCollapsed(next);
      return next;
    });
  }

  return (
    <section className="what-changed panel">
      <header className="panel-header">
        <h3>What Changed</h3>
        <div className="what-changed-actions">
          {!collapsed && changes.length > DEFAULT_RECEIPT_LIMIT ? (
            <button
              type="button"
              className="text-btn"
              onClick={() => setExpanded((prev) => !prev)}
            >
              {expanded ? "Top 5" : "Expand"}
            </button>
          ) : null}
          <button type="button" className="text-btn" onClick={toggleCollapsed}>
            {collapsed ? "Show" : "Hide"}
          </button>
        </div>
      </header>
      {!collapsed ? <p className="panel-meta">{changes.length} tracked updates</p> : null}
      {!collapsed && (
        <ul className="change-list">
          {changes.length === 0 ? (
            <li className="muted">No tracked changes yet.</li>
          ) : (
            visibleChanges.map((change) => <li key={change.id}>{change.text}</li>)
          )}
        </ul>
      )}
    </section>
  );
}
