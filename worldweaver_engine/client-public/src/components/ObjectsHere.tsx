// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getMyObjects,
  getObjectExchanges,
  postExchangeDecision,
  postExchangeOffer,
  postGiveObject,
  postLeaveOnStoop,
  postPickUpObject,
  postPutDownObject,
} from "../api/ww";
import type {
  DurableObjectView,
  ObjectExchangeOfferOption,
  ObjectExchanges,
  StoopShell,
} from "../api/types";
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

const EMPTY_EXCHANGES: ObjectExchanges = {
  exchanges: [],
  count: 0,
  offer_options: [],
};

function recipientLabel(option: ObjectExchangeOfferOption): string {
  const first = option.requested_objects[0];
  return first ? `the person carrying ${first.name}` : "the other person";
}

function ExchangeOfferForm({
  option,
  carried,
  busy,
  onOffer,
}: {
  option: ObjectExchangeOfferOption;
  carried: DurableObjectView[];
  busy: boolean;
  onOffer: (offeredObjectId: string, requestedObjectId: string) => void;
}) {
  const [offeredObjectId, setOfferedObjectId] = useState(carried[0]?.object_id ?? "");
  const [requestedObjectId, setRequestedObjectId] = useState(
    option.requested_objects[0]?.object_id ?? "",
  );

  useEffect(() => {
    if (!carried.some((object) => object.object_id === offeredObjectId)) {
      setOfferedObjectId(carried[0]?.object_id ?? "");
    }
  }, [carried, offeredObjectId]);

  useEffect(() => {
    if (!option.requested_objects.some((object) => object.object_id === requestedObjectId)) {
      setRequestedObjectId(option.requested_objects[0]?.object_id ?? "");
    }
  }, [option.requested_objects, requestedObjectId]);

  if (!offeredObjectId || !requestedObjectId) return null;

  return (
    <details className="object-exchange-offer">
      <summary>Offer a swap with {recipientLabel(option)}</summary>
      <label>
        You offer
        <select value={offeredObjectId} onChange={(event) => setOfferedObjectId(event.target.value)}>
          {carried.map((object) => (
            <option key={object.object_id} value={object.object_id}>{object.name}</option>
          ))}
        </select>
      </label>
      <label>
        You ask for
        <select value={requestedObjectId} onChange={(event) => setRequestedObjectId(event.target.value)}>
          {option.requested_objects.map((object) => (
            <option key={object.object_id} value={object.object_id}>{object.name}</option>
          ))}
        </select>
      </label>
      <button
        className="stoop-take"
        disabled={busy}
        onClick={() => onOffer(offeredObjectId, requestedObjectId)}
      >
        Offer this exact swap
      </button>
      <p className="stoop-entry-desc">Nothing moves unless the other person accepts these exact terms.</p>
    </details>
  );
}

/** What you carry, what lies here, and voluntary custody changes with people here. */
export function ObjectsHere({ location, sessionId, stoops, refreshKey, onChanged }: Props) {
  const [objects, setObjects] = useState<DurableObjectView[]>([]);
  const [exchanges, setExchanges] = useState<ObjectExchanges>(EMPTY_EXCHANGES);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const myActorId = getPlayer()?.actor_id ?? "";

  const refresh = useCallback(async () => {
    const [nextObjects, nextExchanges] = await Promise.all([
      getMyObjects(sessionId).catch(() => ({ objects: [], count: 0 })),
      getObjectExchanges(sessionId).catch(() => EMPTY_EXCHANGES),
    ]);
    setObjects(nextObjects.objects ?? []);
    setExchanges(nextExchanges);
  }, [sessionId]);

  useEffect(() => {
    void refresh();
  }, [location, refresh, refreshKey]);

  // Other people can change object custody and answer an exchange while this panel is open.
  usePoll(refresh, 10_000);

  const carried = useMemo(
    () => objects.filter((object) => object.attachment.kind === "custody" && object.attachment.actor_id === myActorId),
    [myActorId, objects],
  );
  const lyingHere = objects.filter((object) => object.attachment.kind === "place");
  const openExchanges = exchanges.exchanges.filter((exchange) => exchange.status === "open");
  const firstStoopWithRoom = stoops.find((stoop) => stoop.space_remaining > 0);

  async function act(key: string, verb: () => Promise<unknown>, success: string) {
    if (busyKey) return;
    setBusyKey(key);
    setError("");
    setNotice("");
    try {
      await verb();
      setNotice(success);
      await refresh();
      onChanged();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "That action could not be completed.");
      await refresh();
    } finally {
      setBusyKey(null);
    }
  }

  if (carried.length === 0 && lyingHere.length === 0 && openExchanges.length === 0) return null;

  return (
    <>
      {notice && <p className="object-notice" role="status">{notice}</p>}
      {error && <p className="object-error" role="alert">{error}</p>}

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
                  disabled={busyKey != null}
                  onClick={() => void act(
                    `place:${object.object_id}`,
                    () => postPutDownObject(object.object_id, sessionId),
                    `${object.name} is now lying here.`,
                  )}
                >
                  Put it down here
                </button>
                {firstStoopWithRoom && (
                  <button
                    className="stoop-take"
                    disabled={busyKey != null}
                    onClick={() => void act(
                      `stoop:${object.object_id}`,
                      () => postLeaveOnStoop(firstStoopWithRoom.stoop_id, object.object_id, sessionId),
                      `${object.name} is waiting on ${firstStoopWithRoom.title}.`,
                    )}
                  >
                    Leave on {firstStoopWithRoom.title}
                  </button>
                )}
                {exchanges.offer_options.map((option) => (
                  <button
                    key={`${object.object_id}:give:${option.recipient_actor_id}`}
                    className="stoop-take"
                    disabled={busyKey != null}
                    onClick={() => void act(
                      `give:${object.object_id}:${option.recipient_actor_id}`,
                      () => postGiveObject(object.object_id, sessionId, option.recipient_session_id),
                      `You gave ${object.name} to ${recipientLabel(option)}.`,
                    )}
                  >
                    Give to {recipientLabel(option)}
                  </button>
                ))}
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
                {object.can_pick_up ? (
                  <button
                    className="stoop-take"
                    disabled={busyKey != null}
                    onClick={() => void act(
                      `pickup:${object.object_id}`,
                      () => postPickUpObject(object.object_id, sessionId),
                      `You picked up ${object.name}.`,
                    )}
                  >
                    Pick it up
                  </button>
                ) : (
                  <span className="stoop-entry-desc">Only the person who put this down can pick it back up.</span>
                )}
              </div>
            </div>
          ))}
        </section>
      )}

      {(openExchanges.length > 0 || (carried.length > 0 && exchanges.offer_options.length > 0)) && (
        <section className="place-section">
          <h3 className="place-section-title">Object exchanges</h3>
          {openExchanges.map((exchange) => (
            <div key={exchange.exchange_id} className="stoop-entry">
              <span className="stoop-entry-name">
                {exchange.offered_object.name} for {exchange.requested_object.name}
              </span>
              <span className="stoop-entry-desc">
                {exchange.viewer_role === "recipient"
                  ? `Someone here offered their ${exchange.offered_object.name} for your ${exchange.requested_object.name}.`
                  : `You offered your ${exchange.offered_object.name} for their ${exchange.requested_object.name}.`}
                {!exchange.counterpart_present && " The other person is no longer here."}
              </span>
              <div className="object-actions">
                {exchange.can_accept && (
                  <button className="stoop-take" disabled={busyKey != null} onClick={() => void act(
                    `exchange:${exchange.exchange_id}:accept`,
                    () => postExchangeDecision(exchange.exchange_id, sessionId, "accept"),
                    "You accepted. Both objects changed hands together.",
                  )}>Accept this exact swap</button>
                )}
                {exchange.can_decline && (
                  <button className="stoop-take" disabled={busyKey != null} onClick={() => void act(
                    `exchange:${exchange.exchange_id}:decline`,
                    () => postExchangeDecision(exchange.exchange_id, sessionId, "decline"),
                    "You declined. Neither object moved.",
                  )}>Decline</button>
                )}
                {exchange.can_cancel && (
                  <button className="stoop-take" disabled={busyKey != null} onClick={() => void act(
                    `exchange:${exchange.exchange_id}:cancel`,
                    () => postExchangeDecision(exchange.exchange_id, sessionId, "cancel"),
                    "You cancelled your offer. Neither object moved.",
                  )}>Cancel my offer</button>
                )}
              </div>
            </div>
          ))}
          {carried.length > 0 && exchanges.offer_options.map((option) => (
            <ExchangeOfferForm
              key={option.recipient_actor_id}
              option={option}
              carried={carried}
              busy={busyKey != null}
              onOffer={(offeredObjectId, requestedObjectId) => void act(
                `exchange-offer:${option.recipient_actor_id}`,
                () => postExchangeOffer(
                  sessionId,
                  option.recipient_session_id,
                  offeredObjectId,
                  requestedObjectId,
                ),
                "You made an exact exchange offer. Nothing moves until it is accepted.",
              )}
            />
          ))}
        </section>
      )}
    </>
  );
}
