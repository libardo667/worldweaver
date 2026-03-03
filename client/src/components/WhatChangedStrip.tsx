import { useEffect, useMemo, useState } from "react";
import type { ChangeItem, TurnPhase } from "../types";
import {
  loadWhatChangedCollapsed,
  saveWhatChangedCollapsed,
} from "../state/sessionStore";
import { DEFAULT_RECEIPT_LIMIT } from "../utils/diffVars";

type WhatChangedStripProps = {
  changes: ChangeItem[];
  pending?: boolean;
  phase?: TurnPhase;
};

function formatPhaseLabel(phase: TurnPhase): string {
  if (phase === "interpreting") {
    return "Interpreting";
  }
  if (phase === "confirming") {
    return "Confirming";
  }
  if (phase === "rendering") {
    return "Rendering";
  }
  if (phase === "weaving_ahead") {
    return "Weaving ahead";
  }
  return "Idle";
}

export function WhatChangedStrip({
  changes,
  pending = false,
  phase = "idle",
}: WhatChangedStripProps) {
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
      {!collapsed ? (
        <p className="panel-meta">
          {pending
            ? `Weaving phase: ${formatPhaseLabel(phase)}`
            : `${changes.length} tracked updates`}
        </p>
      ) : null}
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
