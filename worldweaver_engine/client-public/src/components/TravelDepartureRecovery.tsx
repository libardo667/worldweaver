// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useState } from "react";
import { postRetryTravelDeparture } from "../api/ww";
import type { PendingDeparture } from "../session/store";

type Props = {
  pending: PendingDeparture;
  onDeparted: (destinationClientUrl: string, travelId: string) => void;
};

export function TravelDepartureRecovery({ pending, onDeparted }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function retry() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await postRetryTravelDeparture(pending.travel_id);
      const destinationUrl = String(result.handoff.destination_client_url || pending.destination_client_url || "").trim();
      if (result.handoff.status === "traveling" && destinationUrl) {
        onDeparted(destinationUrl, result.handoff.travel_id);
        return;
      }
      setError(result.message || result.handoff.last_error || "The network still has not confirmed departure.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The departure still could not be confirmed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="threshold">
      <div className="threshold-card" role="dialog" aria-labelledby="departure-recovery-title">
        <p className="threshold-kicker">Between cities</p>
        <h1 id="departure-recovery-title" className="threshold-title">Your departure needs one more check</h1>
        <p className="threshold-summary">
          You are no longer present in the source city. The network has kept the trip ID so it can finish safely without putting you back in two places.
        </p>
        {error && <p className="join-error" role="alert">{error}</p>}
        <div className="threshold-actions">
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void retry()}>
            {busy ? "Checking…" : "Retry departure"}
          </button>
        </div>
      </div>
    </div>
  );
}
