// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useEffect, useMemo, useState } from "react";
import { getTravelDestinations, postTravelDeparture } from "../api/ww";
import type { TravelNode, TravelRoute, TravelResponse } from "../api/types";
import {
  setPendingDeparture,
  type PendingDeparture,
} from "../session/store";

type Props = {
  location: string;
  sessionId: string;
  onDeparted: (destinationClientUrl: string, travelId: string) => void;
  onDeparturePending: (pending: PendingDeparture) => void;
};

type OfferedTrip = { route: TravelRoute; node: TravelNode };

function normalizedPlace(value: string): string {
  return value.trim().toLocaleLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function newTravelId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `trip-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function usableClientUrl(result: TravelResponse, fallback: string): string {
  return String(result.handoff.destination_client_url || fallback || "").trim();
}

export function TravelHere({ location, sessionId, onDeparted, onDeparturePending }: Props) {
  const [routes, setRoutes] = useState<TravelRoute[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getTravelDestinations()
      .then((result) => {
        if (active) setRoutes(result.destinations ?? []);
      })
      .catch(() => {
        if (active) setRoutes([]);
      });
    return () => {
      active = false;
    };
  }, []);

  const offered = useMemo<OfferedTrip[]>(() => {
    const here = normalizedPlace(location);
    return routes.flatMap((route) => {
      if (normalizedPlace(route.departure_place || "") !== here || route.availability !== "available") return [];
      return route.nodes
        .filter((node) => ["healthy", "degraded"].includes(node.status) && Boolean(String(node.client_url || "").trim()))
        .map((node) => ({ route, node }));
    });
  }, [location, routes]);

  function finish(result: TravelResponse, fallbackUrl: string) {
    const destinationUrl = usableClientUrl(result, fallbackUrl);
    const nextPending = { travel_id: result.handoff.travel_id, destination_client_url: destinationUrl };
    if (result.handoff.status === "traveling" && destinationUrl) {
      onDeparted(destinationUrl, result.handoff.travel_id);
      return;
    }
    setPendingDeparture(nextPending);
    onDeparturePending(nextPending);
    setError(result.message || result.handoff.last_error || "The trip has not finished leaving this city yet.");
  }

  async function depart({ route, node }: OfferedTrip) {
    if (busy) return;
    setBusy(true);
    setError("");
    const travelId = newTravelId();
    try {
      const result = await postTravelDeparture(sessionId, route.route_id, node.shard_id, travelId);
      finish(result, String(node.client_url || ""));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "This trip could not start.");
    } finally {
      setBusy(false);
    }
  }

  if (offered.length === 0) return null;

  return (
    <section className="place-section travel-here" aria-labelledby="travel-here-title">
      <h3 id="travel-here-title" className="place-section-title">Travel onward</h3>
      <div className="travel-options">
        {offered.map((trip) => (
          <button
            type="button"
            className="travel-option"
            key={`${trip.route.route_id}:${trip.node.shard_id}`}
            disabled={busy}
            onClick={() => void depart(trip)}
          >
            <strong>{trip.route.arrival_hub || trip.route.to_city_id.replace(/_/g, " ")}</strong>
            <span>
              {trip.route.mode || "route"}
              {trip.route.operator ? ` · ${trip.route.operator}` : ""}
              {trip.route.duration_hours ? ` · ${trip.route.duration_hours} hours` : ""}
            </span>
          </button>
        ))}
      </div>
      {error && <p className="join-error" role="alert">{error}</p>}
    </section>
  );
}
