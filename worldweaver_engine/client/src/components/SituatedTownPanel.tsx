// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getLocalMaking,
  getLocalStoops,
  getObjectExchanges,
  getShardExperience,
  getWorldObjects,
  getWorldStoop,
  postMakeWorldObject,
  postLeaveObjectOnStoop,
  postGiveWorldObject,
  postObjectExchangeDecision,
  postObjectExchangeOffer,
  postPickUpWorldObject,
  postPlaceWorldObject,
  postTakeStoopObject,
  postWithdrawStoopObject,
  type LocalMakingResponse,
  type LocalStoopsResponse,
  type ObjectExchangesResponse,
  type ShardExperienceResponse,
  type WorldObjectsResponse,
  type WorldStoopResponse,
} from "../api/wwClient";

type SituatedTownPanelProps = {
  sessionId: string;
  location: string;
  active: boolean;
  observerMode: boolean;
  peopleHere: Array<{ sessionId: string; name: string }>;
};

const EMPTY_OBJECTS: WorldObjectsResponse = { objects: [], count: 0 };
const EMPTY_MAKING: LocalMakingResponse = { location: "", materials: [], recipes: [] };
const EMPTY_STOOPS: LocalStoopsResponse = { location: "", stoops: [], count: 0 };
const EMPTY_EXCHANGES: ObjectExchangesResponse = { exchanges: [], count: 0, offer_options: [] };

export function SituatedTownPanel({ sessionId, location, active, observerMode, peopleHere }: SituatedTownPanelProps) {
  const [experience, setExperience] = useState<ShardExperienceResponse | null>(null);
  const [objects, setObjects] = useState<WorldObjectsResponse>(EMPTY_OBJECTS);
  const [making, setMaking] = useState<LocalMakingResponse>(EMPTY_MAKING);
  const [stoops, setStoops] = useState<LocalStoopsResponse>(EMPTY_STOOPS);
  const [exchanges, setExchanges] = useState<ObjectExchangesResponse>(EMPTY_EXCHANGES);
  const [openStoop, setOpenStoop] = useState<WorldStoopResponse | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const capabilities = useMemo(
    () => new Set(experience?.entry_disclosure.capabilities.map((item) => item.id) ?? []),
    [experience],
  );

  const refresh = useCallback(async () => {
    if (!active || !sessionId) return;
    setPending(true);
    setError(null);
    setNotice(null);
    setOpenStoop(null);
    try {
      const profile = await getShardExperience();
      setExperience(profile);
      const enabled = new Set(profile.entry_disclosure.capabilities.map((item) => item.id));
      const [nextObjects, nextMaking, nextStoops, nextExchanges] = await Promise.all([
        enabled.has("durable_objects") ? getWorldObjects(sessionId) : Promise.resolve(EMPTY_OBJECTS),
        enabled.has("making") ? getLocalMaking(sessionId) : Promise.resolve(EMPTY_MAKING),
        enabled.has("stoops") ? getLocalStoops(sessionId) : Promise.resolve(EMPTY_STOOPS),
        enabled.has("witnessed_exchange") ? getObjectExchanges(sessionId) : Promise.resolve(EMPTY_EXCHANGES),
      ]);
      setObjects(nextObjects);
      setMaking(nextMaking);
      setStoops(nextStoops);
      setExchanges(nextExchanges);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "This place could not be inspected right now.");
    } finally {
      setPending(false);
    }
  }, [active, sessionId]);

  useEffect(() => {
    void refresh();
  }, [location, refresh]);

  const browseStoop = useCallback(async (stoopId: string) => {
    setPending(true);
    setError(null);
    try {
      setOpenStoop(await getWorldStoop(sessionId, stoopId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "That stoop could not be opened right now.");
    } finally {
      setPending(false);
    }
  }, [sessionId]);

  const makeObject = useCallback(async (recipeId: string) => {
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      const result = await postMakeWorldObject(
        sessionId,
        recipeId,
        `human-make:${crypto.randomUUID()}`,
      );
      await refresh();
      setNotice(result.object?.name ? `You made ${result.object.name}.` : "The object was made.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "That object could not be made right now.");
    } finally {
      setPending(false);
    }
  }, [refresh, sessionId]);

  const moveObject = useCallback(async (objectId: string, command: "place" | "pick-up") => {
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      const key = `human-${command}:${crypto.randomUUID()}`;
      const result = command === "place"
        ? await postPlaceWorldObject(sessionId, objectId, key)
        : await postPickUpWorldObject(sessionId, objectId, key);
      await refresh();
      const name = result.object?.name || "The object";
      setNotice(command === "place" ? `${name} is now here.` : `You picked up ${name}.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "That object could not be moved right now.");
    } finally {
      setPending(false);
    }
  }, [refresh, sessionId]);

  const giveObject = useCallback(async (objectId: string, recipient: { sessionId: string; name: string }) => {
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      const result = await postGiveWorldObject(
        sessionId,
        objectId,
        recipient.sessionId,
        `human-give:${crypto.randomUUID()}`,
      );
      await refresh();
      const name = result.object?.name || "The object";
      setNotice(`You gave ${name} to ${recipient.name}.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "That object could not be given right now.");
    } finally {
      setPending(false);
    }
  }, [refresh, sessionId]);

  const offerExchange = useCallback(async (
    recipientSessionId: string,
    offeredObjectId: string,
    requestedObjectId: string,
  ) => {
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      const result = await postObjectExchangeOffer(
        sessionId,
        recipientSessionId,
        offeredObjectId,
        requestedObjectId,
        `human-exchange-offer:${crypto.randomUUID()}`,
      );
      await refresh();
      const offeredName = result.exchange.offered_object?.name || "your object";
      const requestedName = result.exchange.requested_object?.name || "their object";
      setNotice(`You offered ${offeredName} for ${requestedName}. Nothing moves unless they accept.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "That exchange could not be offered right now.");
    } finally {
      setPending(false);
    }
  }, [refresh, sessionId]);

  const decideExchange = useCallback(async (
    exchangeId: string,
    decision: "accept" | "decline" | "cancel",
  ) => {
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      const result = await postObjectExchangeDecision(
        sessionId,
        exchangeId,
        decision,
        `human-exchange-${decision}:${crypto.randomUUID()}`,
      );
      await refresh();
      setNotice(
        decision === "accept"
          ? "You accepted the exact exchange. Both objects changed hands together."
          : decision === "decline"
            ? "You declined the exchange. Neither object moved."
            : "You cancelled your offer. Neither object moved.",
      );
      if (!result.receipt?.receipt_id) setNotice("The exchange did not change.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "That exchange decision could not be completed.");
    } finally {
      setPending(false);
    }
  }, [refresh, sessionId]);

  const moveStoopObject = useCallback(async (
    command: "leave" | "take" | "withdraw",
    primaryId: string,
    objectId = "",
  ) => {
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      const key = `human-stoop-${command}:${crypto.randomUUID()}`;
      const result = command === "leave"
        ? await postLeaveObjectOnStoop(sessionId, primaryId, objectId, key)
        : command === "take"
          ? await postTakeStoopObject(sessionId, primaryId, key)
          : await postWithdrawStoopObject(sessionId, primaryId, key);
      await refresh();
      const name = result.entry?.object?.name || "The object";
      setNotice(
        command === "leave"
          ? `${name} is now available for another visitor to take.`
          : command === "take"
            ? `You took ${name}.`
            : `You reclaimed ${name}.`,
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "That stoop action could not be completed.");
    } finally {
      setPending(false);
    }
  }, [refresh, sessionId]);

  if (observerMode) {
    return (
      <div className="ww-situated-panel ww-situated-panel--empty">
        <h3>Here</h3>
        <p>Enter the town as yourself to inspect things carried, made, or left at this exact place.</p>
      </div>
    );
  }

  if (!active) {
    return (
      <div className="ww-situated-panel ww-situated-panel--empty">
        <h3>Here</h3>
        <p>Finish entering the town to see what is around you.</p>
      </div>
    );
  }

  const hasGameFeatures = capabilities.size > 0;
  const carried = objects.objects.filter((item) => item.relation === "carried");
  const nearby = objects.objects.filter((item) => item.relation !== "carried");

  return (
    <div className="ww-situated-panel">
      <header className="ww-situated-header">
        <div>
          <p className="ww-situated-kicker">You are here</p>
          <h3>{location || "Unknown place"}</h3>
        </div>
        <button className="ww-situated-refresh" onClick={() => void refresh()} disabled={pending}>
          {pending ? "Looking…" : "Look again"}
        </button>
      </header>

      {error && <p className="ww-situated-error">{error}</p>}
      {notice && <p className="ww-situated-notice">{notice}</p>}
      {!pending && experience && !hasGameFeatures && (
        <p className="ww-situated-empty">This shard has no optional object or making rules.</p>
      )}

      {capabilities.has("durable_objects") && (
        <section className="ww-situated-section">
          <h4>What you carry</h4>
          {carried.length === 0 ? (
            <p className="ww-situated-empty">You are not carrying a durable object.</p>
          ) : (
            <ul className="ww-situated-list">
              {carried.map((item) => (
                <li key={item.object_id}>
                  <strong>{item.name}</strong>
                  <span>{item.description}</span>
                  <button onClick={() => void moveObject(item.object_id, "place")} disabled={pending}>
                    Place here
                  </button>
                  {peopleHere.map((person) => (
                    <button
                      key={`${item.object_id}:${person.sessionId}`}
                      onClick={() => void giveObject(item.object_id, person)}
                      disabled={pending}
                    >
                      Give to {person.name}
                    </button>
                  ))}
                </li>
              ))}
            </ul>
          )}

          <h4>Objects here</h4>
          {nearby.length === 0 ? (
            <p className="ww-situated-empty">No durable objects are lying here.</p>
          ) : (
            <ul className="ww-situated-list">
              {nearby.map((item) => (
                <li key={item.object_id}>
                  <strong>{item.name}</strong>
                  <span>{item.description}</span>
                  {item.can_pick_up && (
                    <button onClick={() => void moveObject(item.object_id, "pick-up")} disabled={pending}>
                      Pick up
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {capabilities.has("making") && (
        <section className="ww-situated-section">
          <h4>Making here</h4>
          {making.materials.length === 0 && making.recipes.length === 0 ? (
            <p className="ww-situated-empty">There are no materials or recipes at this exact place.</p>
          ) : (
            <>
              {making.materials.map((material) => (
                <div className="ww-situated-row" key={material.material_id}>
                  <span>{material.title}</span>
                  <span>{material.available_units} / {material.capacity_units}</span>
                </div>
              ))}
              <ul className="ww-situated-list">
                {making.recipes.map((recipe) => (
                  <li key={recipe.recipe_id}>
                    <strong>{recipe.title}</strong>
                    <span>{recipe.description}</span>
                    <small>{recipe.can_make ? "Materials available" : "Missing materials"}</small>
                    <button
                      onClick={() => void makeObject(recipe.recipe_id)}
                      disabled={pending || !recipe.can_make}
                    >
                      Make this
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {capabilities.has("witnessed_exchange") && (
        <section className="ww-situated-section">
          <h4>Object exchanges</h4>
          {exchanges.exchanges.length === 0 ? (
            <p className="ww-situated-empty">You have no object exchanges here.</p>
          ) : (
            <ul className="ww-situated-list">
              {exchanges.exchanges.map((exchange) => {
                const counterpartActorId = exchange.viewer_role === "recipient"
                  ? exchange.proposer_actor_id
                  : exchange.recipient_actor_id;
                const counterpartSessionId = exchanges.offer_options.find(
                  (option) => option.recipient_actor_id === counterpartActorId,
                )?.recipient_session_id;
                const counterpartName = peopleHere.find(
                  (person) => person.sessionId === counterpartSessionId,
                )?.name ?? "The other person";
                return (
                  <li key={exchange.exchange_id}>
                    <strong>{exchange.offered_object.name} for {exchange.requested_object.name}</strong>
                    <span>
                      {exchange.viewer_role === "recipient"
                        ? `${counterpartName} offered their ${exchange.offered_object.name} for your ${exchange.requested_object.name}.`
                        : `You offered your ${exchange.offered_object.name} for ${counterpartName}'s ${exchange.requested_object.name}.`}
                    </span>
                    <small>Status: {exchange.status}{exchange.status === "open" && !exchange.counterpart_present ? "; the other person is not here" : ""}</small>
                    {exchange.can_accept && (
                      <button onClick={() => void decideExchange(exchange.exchange_id, "accept")} disabled={pending}>
                        Accept this exact swap
                      </button>
                    )}
                    {exchange.can_decline && (
                      <button onClick={() => void decideExchange(exchange.exchange_id, "decline")} disabled={pending}>
                        Decline
                      </button>
                    )}
                    {exchange.can_cancel && (
                      <button onClick={() => void decideExchange(exchange.exchange_id, "cancel")} disabled={pending}>
                        Cancel my offer
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}

          <h4>Offer a swap</h4>
          {carried.length === 0 || exchanges.offer_options.length === 0 ? (
            <p className="ww-situated-empty">You need to carry an object, and someone here must carry one too.</p>
          ) : (
            <ul className="ww-situated-list">
              {exchanges.offer_options.flatMap((option) => {
                const recipientName = peopleHere.find(
                  (person) => person.sessionId === option.recipient_session_id,
                )?.name ?? "the other person";
                return option.requested_objects.flatMap((requested) => carried.map((offered) => (
                  <li key={`${option.recipient_session_id}:${offered.object_id}:${requested.object_id}`}>
                    <span>Offer your {offered.name} for {recipientName}'s {requested.name}.</span>
                    <button
                      onClick={() => void offerExchange(
                        option.recipient_session_id,
                        offered.object_id,
                        requested.object_id,
                      )}
                      disabled={pending}
                    >
                      Make this offer
                    </button>
                  </li>
                )));
              })}
            </ul>
          )}
        </section>
      )}

      {capabilities.has("stoops") && (
        <section className="ww-situated-section">
          <h4>Stoops here</h4>
          {stoops.stoops.length === 0 ? (
            <p className="ww-situated-empty">There is no stoop at this exact place.</p>
          ) : (
            <ul className="ww-situated-list">
              {stoops.stoops.map((stoop) => (
                <li key={stoop.stoop_id}>
                  <strong>{stoop.title}</strong>
                  <span>{stoop.prompt}</span>
                  <small>{stoop.active_count} of {stoop.capacity} spaces in use</small>
                  <button onClick={() => void browseStoop(stoop.stoop_id)} disabled={pending}>
                    Look inside
                  </button>
                  {carried.map((item) => (
                    <button
                      key={`${stoop.stoop_id}:${item.object_id}`}
                      onClick={() => void moveStoopObject("leave", stoop.stoop_id, item.object_id)}
                      disabled={pending || stoop.space_remaining <= 0}
                    >
                      Leave {item.name} for someone to take
                    </button>
                  ))}
                </li>
              ))}
            </ul>
          )}

          {openStoop && (
            <div className="ww-situated-stoop-contents">
              <h4>On {openStoop.stoop.title}</h4>
              {openStoop.entries.length === 0 ? (
                <p className="ww-situated-empty">Nothing has been left here.</p>
              ) : (
                <ul className="ww-situated-list">
                  {openStoop.entries.map((entry) => (
                    <li key={entry.entry_id}>
                      <strong>{entry.object.name}</strong>
                      <span>{entry.object.description}</span>
                      {entry.can_take && (
                        <button onClick={() => void moveStoopObject("take", entry.entry_id)} disabled={pending}>
                          Take this
                        </button>
                      )}
                      {entry.can_withdraw && (
                        <button onClick={() => void moveStoopObject("withdraw", entry.entry_id)} disabled={pending}>
                          Reclaim what you left
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
