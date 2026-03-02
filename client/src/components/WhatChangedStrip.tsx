import { useState } from "react";
import type { ChangeItem } from "../types";

type WhatChangedStripProps = {
  changes: ChangeItem[];
};

export function WhatChangedStrip({ changes }: WhatChangedStripProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <section className="what-changed panel">
      <header className="panel-header">
        <h3>What Changed</h3>
        <button
          type="button"
          className="text-btn"
          onClick={() => setCollapsed((prev) => !prev)}
        >
          {collapsed ? "Expand" : "Collapse"}
        </button>
      </header>
      {!collapsed && (
        <ul className="change-list">
          {changes.length === 0 ? (
            <li className="muted">No tracked changes yet.</li>
          ) : (
            changes.map((change) => <li key={change.id}>{change.text}</li>)
          )}
        </ul>
      )}
    </section>
  );
}
