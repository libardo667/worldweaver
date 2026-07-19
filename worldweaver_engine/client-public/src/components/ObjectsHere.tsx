// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useEffect, useState } from "react";
import { getMyObjects, postLeaveOnStoop, postPickUpObject, postPutDownObject } from "../api/ww";
import type { DurableObjectView, StoopShell } from "../api/types";
import { usePoll } from "../hooks/usePoll";
import { getPlayer } from "../session/store";

type Props = {
  location: string;
  sessionId: string;
  stoops: StoopShell[];
  /** Bumped by the parent when the world changed (something was made/taken). */
  refreshKey: number;
  /** Called after this component changes the world (moved an object). */
  onChanged: () => void;
};

/** What you carry and what lies at this place, with the honest verbs. */
export function ObjectsHere({ location, sessionId, stoops, refreshKey, onChanged }: Props) {
  const [objects, setObjects] = useState<DurableObjectView[]>([]);
  const [busyObjectId, setBusyObjectId] = useState<string | null>(null);
  const myActorId = getPlayer()?.actor_id ?? "";

  useEffect(() => {
    let live = true;
    getMyObjects(sessionId)
      .then((result) => {
        if (live) setObjects(result.objects ?? []);
      })
      .catch(() => {
        if (live) setObjects([]);
      });
    return () => {
      live = false;
    };
  }, [sessionId, location, refreshKey]);

  // Other people place and pick things up too.
  usePoll(async () => {
    try {
      const result = await getMyObjects(sessionId);
      setObjects(result.objects ?? []);
    } catch {
      // Keep the last truthful reading.
    }
  }, 10_000);

  const carried = objects.filter((o) => o.attachment.kind === "custody" && o.attachment.actor_id === myActorId);
  const lyingHere = objects.filter((o) => o.attachment.kind === "place");
  const firstStoopWithRoom = stoops.find((s) => s.space_remaining > 0);

  async function act(objectId: string, verb: () => Promise<unknown>) {
    if (busyObjectId) return;
    setBusyObjectId(objectId);
    try {
      await verb();
    } catch {
      // The refresh below shows the true state either way.
    } finally {
      setBusyObjectId(null);
      onChanged();
    }
  }

  if (carried.length === 0 && lyingHere.length === 0) return null;

  return (
    <>
      {carried.length > 0 && (
        <section className="place-section">
          <h3 className="place-section-title">You are carrying</h3>
          {carried.map((object) => (
            <div key={object.object_id} className="stoop-entry">
              <span className="stoop-entry-name">{object.name}</span>
              {object.description && <span className="stoop-entry-desc">{object.description}</span>}
              <div className="object-actions">
                <button
                  className="stoop-take"
                  disabled={busyObjectId != null}
                  onClick={() => act(object.object_id, () => postPutDownObject(object.object_id, sessionId))}
                >
                  Put it down here
                </button>
                {firstStoopWithRoom && (
                  <button
                    className="stoop-take"
                    disabled={busyObjectId != null}
                    onClick={() => act(object.object_id, () => postLeaveOnStoop(firstStoopWithRoom.stoop_id, object.object_id, sessionId))}
                  >
                    Leave on {firstStoopWithRoom.title}
                  </button>
                )}
              </div>
            </div>
          ))}
        </section>
      )}
      {lyingHere.length > 0 && (
        <section className="place-section">
          <h3 className="place-section-title">Lying here</h3>
          {lyingHere.map((object) => (
            <div key={object.object_id} className="stoop-entry">
              <span className="stoop-entry-name">{object.name}</span>
              {object.description && <span className="stoop-entry-desc">{object.description}</span>}
              <div className="object-actions">
                <button
                  className="stoop-take"
                  disabled={busyObjectId != null}
                  onClick={() => act(object.object_id, () => postPickUpObject(object.object_id, sessionId))}
                >
                  Pick it up
                </button>
              </div>
            </div>
          ))}
        </section>
      )}
    </>
  );
}
