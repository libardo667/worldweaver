import { useState } from "react";

import type { VarsRecord, WorldEvent } from "../types";
import {
  buildShareTeaser,
  copyTextToClipboard,
  exportRunArtifacts,
} from "../utils/exportRun";

type ExportPanelProps = {
  sessionId: string;
  varsSnapshot: VarsRecord;
  events: WorldEvent[];
  becauseOfEvents: WorldEvent[];
  pinnedEvents: WorldEvent[];
};

export function ExportPanel({
  sessionId,
  varsSnapshot,
  events,
  becauseOfEvents,
  pinnedEvents,
}: ExportPanelProps) {
  const [status, setStatus] = useState("");

  function handleExport() {
    exportRunArtifacts(
      sessionId,
      varsSnapshot,
      events,
      becauseOfEvents,
      pinnedEvents,
    );
    setStatus("Downloaded run.json and chronicle.md.");
  }

  async function handleCopyShareText() {
    const teaser = buildShareTeaser(sessionId, events, becauseOfEvents);
    const copied = await copyTextToClipboard(teaser);
    if (copied) {
      setStatus("Copied share teaser to clipboard.");
      return;
    }
    setStatus("Could not copy automatically. Try again after enabling clipboard access.");
  }

  return (
    <section className="reflect-export-actions" aria-label="Export controls">
      <button type="button" className="text-btn" onClick={handleExport}>
        Export run.json + chronicle.md
      </button>
      <button type="button" className="text-btn" onClick={handleCopyShareText}>
        Copy share text
      </button>
      {status ? <p className="muted export-status">{status}</p> : null}
    </section>
  );
}
