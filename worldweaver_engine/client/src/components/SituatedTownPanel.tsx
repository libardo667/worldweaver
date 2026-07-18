// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getLocalMaking,
  getLocalStoops,
  getShardExperience,
  getWorldObjects,
  getWorldStoop,
  postMakeWorldObject,
  type LocalMakingResponse,
  type LocalStoopsResponse,
  type ShardExperienceResponse,
  type WorldObjectsResponse,
  type WorldStoopResponse,
} from "../api/wwClient";

type SituatedTownPanelProps = {
  sessionId: string;
  location: string;
  active: boolean;
  observerMode: boolean;
};

const EMPTY_OBJECTS: WorldObjectsResponse = { objects: [], count: 0 };
const EMPTY_MAKING: LocalMakingResponse = { location: "", materials: [], recipes: [] };
const EMPTY_STOOPS: LocalStoopsResponse = { location: "", stoops: [], count: 0 };

export function SituatedTownPanel({ sessionId, location, active, observerMode }: SituatedTownPanelProps) {
  const [experience, setExperience] = useState<ShardExperienceResponse | null>(null);
  const [objects, setObjects] = useState<WorldObjectsResponse>(EMPTY_OBJECTS);
  const [making, setMaking] = useState<LocalMakingResponse>(EMPTY_MAKING);
  const [stoops, setStoops] = useState<LocalStoopsResponse>(EMPTY_STOOPS);
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
      const [nextObjects, nextMaking, nextStoops] = await Promise.all([
        enabled.has("durable_objects") ? getWorldObjects(sessionId) : Promise.resolve(EMPTY_OBJECTS),
        enabled.has("making") ? getLocalMaking(sessionId) : Promise.resolve(EMPTY_MAKING),
        enabled.has("stoops") ? getLocalStoops(sessionId) : Promise.resolve(EMPTY_STOOPS),
      ]);
      setObjects(nextObjects);
      setMaking(nextMaking);
      setStoops(nextStoops);
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
