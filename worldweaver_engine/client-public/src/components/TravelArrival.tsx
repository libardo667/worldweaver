// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useCallback, useEffect, useState } from "react";
import { ApiError, postRetryTravelArrival, postTravelArrival } from "../api/ww";
import type { EntryInfo, TravelResponse } from "../api/types";
import { getJwt, getPlayer, getSessionId, mintSessionId, setStandingPlace } from "../session/store";
import { JoinFlow } from "./JoinFlow";

type Props = {
  travelId: string;
  entry: EntryInfo | null;
  onArrived: (place: string) => void;
  onClose: () => void;
};

export function TravelArrival({ travelId, entry, onArrived, onClose }: Props) {
  const [busy, setBusy] = useState(false);
  const [needsLogin, setNeedsLogin] = useState(!getJwt() || !getPlayer());
  const [recoverable, setRecoverable] = useState(false);
  const [error, setError] = useState("");

  const handleResult = useCallback(
    (result: TravelResponse) => {
      const place = String(result.place || "").trim();
      if (result.handoff.status === "arrived" && place) {
        setStandingPlace(place);
        onArrived(place);
        return;
      }
      setRecoverable(Boolean(result.recoverable) || ["prepared", "session_booted"].includes(result.handoff.status));
      setError(result.message || result.handoff.last_error || "This arrival has not finished yet.");
    },
    [onArrived],
  );

  const arrive = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const sessionId = getSessionId() || mintSessionId();
      handleResult(await postTravelArrival(travelId, sessionId));
    } catch (cause) {
      if (cause instanceof ApiError && [401, 403].includes(cause.status)) {
        setNeedsLogin(true);
      }
      setError(cause instanceof Error ? cause.message : "This city could not receive the trip.");
    } finally {
      setBusy(false);
    }
  }, [busy, handleResult, travelId]);

  useEffect(() => {
    if (needsLogin) return;
    void arrive();
    // Arrival is idempotent. Run once when an authenticated arrival page opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [needsLogin]);

  async function retry() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      handleResult(await postRetryTravelArrival(travelId));
    } catch (cause) {
      if (cause instanceof ApiError && [401, 403].includes(cause.status)) setNeedsLogin(true);
      setError(cause instanceof Error ? cause.message : "This arrival still could not be confirmed.");
    } finally {
      setBusy(false);
    }
  }

  if (needsLogin) {
    return (
      <JoinFlow
        entry={entry}
        suggestedPlace={null}
        arrival={{
          onAuthenticated: async () => {
            setNeedsLogin(false);
          },
        }}
        onJoined={() => undefined}
        onClose={onClose}
      />
    );
  }

  return (
    <div className="threshold">
      <div className="threshold-card" role="dialog" aria-labelledby="arrival-title">
        <p className="threshold-kicker">Between cities</p>
        <h1 id="arrival-title" className="threshold-title">Finishing your arrival</h1>
        <p className="threshold-summary">
          {busy ? "The destination is checking your trip…" : error || "The destination is preparing a local place for you."}
        </p>
        <div className="threshold-actions">
          {recoverable && (
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void retry()}>
              {busy ? "Checking…" : "Retry arrival"}
            </button>
          )}
          {!busy && !recoverable && error && (
            <button type="button" className="btn btn-primary" onClick={() => void arrive()}>
              Try again
            </button>
          )}
          <button type="button" className="btn btn-quiet" onClick={onClose}>Return to the map</button>
        </div>
      </div>
    </div>
  );
}
