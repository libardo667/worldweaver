// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useCallback, useRef, useState } from "react";
import type { PendingSpaceAccessRequests, SpaceAccessStatus } from "../api/types";
import {
  getPendingSpaceAccessRequests,
  getSpaceAccess,
  postResolveSpaceAccessRequest,
  postSpaceAccessRequest,
  postSpaceMode,
} from "../api/ww";
import { usePoll } from "../hooks/usePoll";

type Props = {
  location: string;
  sessionId: string;
};

const EMPTY_REQUESTS: PendingSpaceAccessRequests = { location: "", requests: [], count: 0 };

function doorSummary(access: SpaceAccessStatus): string {
  if (access.is_controller) return "You decide who may enter this place.";
  if (access.request_pending) return "Your knock is waiting for an answer.";
  if (access.can_enter && access.admitted) return "You have permission to enter.";
  if (access.mode === "closed") return "This place is closed to new entry.";
  if (access.mode === "private") return "This is a private place.";
  if (access.mode === "requestable") return "You need to ask before entering.";
  return "This place is open.";
}

/** The rules at one doorway. This intentionally never becomes a town-wide access dashboard. */
export function AccessHere({ location, sessionId }: Props) {
  const [access, setAccess] = useState<SpaceAccessStatus | null>(null);
  const [requests, setRequests] = useState<PendingSpaceAccessRequests>(EMPTY_REQUESTS);
  const [controllerNote, setControllerNote] = useState("");
  const [requestNote, setRequestNote] = useState("");
  const [mode, setMode] = useState<"public" | "requestable" | "private" | "closed">("private");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const editingRuleRef = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const result = await getSpaceAccess(sessionId, location);
      setAccess(result.access);
      if (!editingRuleRef.current) {
        setMode(result.access.mode as typeof mode);
        setControllerNote(result.access.note ?? "");
      }
      if (result.access.is_controller) {
        setRequests(await getPendingSpaceAccessRequests(sessionId, location));
      } else {
        setRequests(EMPTY_REQUESTS);
      }
    } catch {
      // Ordinary shards do not opt into door rules. They should show no
      // broken-looking controls just because this optional capability is off.
      setAccess(null);
      setRequests(EMPTY_REQUESTS);
    }
  }, [location, sessionId]);

  usePoll(refresh, access?.is_controller ? 8_000 : 20_000);

  async function act(verb: () => Promise<unknown>, success: string) {
    if (busy) return;
    setBusy(true);
    setNotice("");
    setError("");
    try {
      await verb();
      setNotice(success);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "That doorway action did not work.");
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  // Revision zero is the server's explicit "no restriction here" result.
  if (!access || (access.revision === 0 && !access.is_controller)) return null;

  return (
    <section className="place-section access-here" aria-labelledby="access-here-title">
      <h3 id="access-here-title" className="place-section-title">At the door</h3>
      <p className="access-summary">{doorSummary(access)}</p>
      {access.note && !access.is_controller && <p className="access-note">{access.note}</p>}
      {notice && <p className="object-notice" role="status">{notice}</p>}
      {error && <p className="object-error" role="alert">{error}</p>}

      {access.can_request && (
        <div className="access-request-form">
          <label htmlFor="access-request-note">A short note (optional)</label>
          <textarea
            id="access-request-note"
            value={requestNote}
            maxLength={500}
            onChange={(event) => setRequestNote(event.target.value)}
            placeholder="Say why you are knocking"
          />
          <button
            className="stoop-take"
            disabled={busy}
            onClick={() => void act(
              () => postSpaceAccessRequest(sessionId, location, requestNote),
              "Your knock is waiting for an answer.",
            )}
          >
            Knock and ask
          </button>
        </div>
      )}

      {access.is_controller && (
        <>
          <div className="access-mode-form">
            <label htmlFor="access-mode">Who may enter</label>
            <select id="access-mode" value={mode} onChange={(event) => {
              editingRuleRef.current = true;
              setMode(event.target.value as typeof mode);
            }}>
              <option value="public">Anyone</option>
              <option value="requestable">People who ask</option>
              <option value="private">Invited people only</option>
              <option value="closed">No new entry</option>
            </select>
            <label htmlFor="access-controller-note">Note at the door</label>
            <textarea
              id="access-controller-note"
              value={controllerNote}
              maxLength={500}
              onChange={(event) => {
                editingRuleRef.current = true;
                setControllerNote(event.target.value);
              }}
              placeholder="Optional note for visitors"
            />
            <button
              className="stoop-take"
              disabled={busy || (mode === access.mode && controllerNote === access.note)}
              onClick={() => void act(
                () => {
                  editingRuleRef.current = false;
                  return postSpaceMode(sessionId, location, mode, controllerNote);
                },
                "The rule at this door has changed.",
              )}
            >
              Save door rule
            </button>
          </div>

          {requests.requests.length > 0 && (
            <div className="access-requests">
              <h4>People knocking</h4>
              {requests.requests.map((request, index) => (
                <div className="access-request" key={request.request_id}>
                  <span>
                    Visitor {index + 1}{request.note ? `: ${request.note}` : " left no note."}
                  </span>
                  <div className="object-actions">
                    <button className="stoop-take" disabled={busy} onClick={() => void act(
                      () => postResolveSpaceAccessRequest(request.request_id, sessionId, "admitted"),
                      "You let them in.",
                    )}>Let them in</button>
                    <button className="stoop-take" disabled={busy} onClick={() => void act(
                      () => postResolveSpaceAccessRequest(request.request_id, sessionId, "denied"),
                      "You declined the request.",
                    )}>Decline</button>
                  </div>
                </div>
              ))}
            </div>
          )}

        </>
      )}
    </section>
  );
}
