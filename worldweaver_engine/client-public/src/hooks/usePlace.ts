// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useEffect, useState } from "react";
import { getNearbyLandmarks, getPlaceContext, getStoopsAt } from "../api/ww";
import type { Landmark, PlaceContext, StoopShell } from "../api/types";
import { usePoll } from "./usePoll";

// Geography doesn't move: context prose and landmarks are cached for the
// whole page load. Stoops are living furniture and are refetched per visit.
const contextCache = new Map<string, PlaceContext | null>();
const landmarkCache = new Map<string, Landmark[]>();

export type PlaceDetails = {
  context: PlaceContext | null;
  landmarks: Landmark[];
  stoops: StoopShell[];
};

export function usePlace(name: string | null, stoopRefreshKey = 0): PlaceDetails {
  const [context, setContext] = useState<PlaceContext | null>(null);
  const [landmarks, setLandmarks] = useState<Landmark[]>([]);
  const [stoops, setStoops] = useState<StoopShell[]>([]);

  useEffect(() => {
    if (!name) {
      setContext(null);
      setLandmarks([]);
      setStoops([]);
      return;
    }
    let live = true;
    setStoops([]);

    if (contextCache.has(name)) {
      setContext(contextCache.get(name) ?? null);
    } else {
      setContext(null);
      getPlaceContext(name)
        .then((result) => {
          contextCache.set(name, result);
          if (live) setContext(result);
        })
        .catch(() => contextCache.set(name, null));
    }

    if (landmarkCache.has(name)) {
      setLandmarks(landmarkCache.get(name) ?? []);
    } else {
      setLandmarks([]);
      getNearbyLandmarks(name)
        .then((result) => {
          landmarkCache.set(name, result.landmarks ?? []);
          if (live) setLandmarks(result.landmarks ?? []);
        })
        .catch(() => landmarkCache.set(name, []));
    }

    getStoopsAt(name)
      .then((result) => {
        if (live) setStoops(result.stoops ?? []);
      })
      .catch(() => {
        if (live) setStoops([]);
      });

    return () => {
      live = false;
    };
  }, [name, stoopRefreshKey]);

  // Stoops are living furniture other people change too — keep shell counts
  // honest while someone is watching this place.
  usePoll(async () => {
    if (!name) return;
    try {
      const result = await getStoopsAt(name);
      setStoops(result.stoops ?? []);
    } catch {
      // Keep the last truthful reading.
    }
  }, name ? 15_000 : null);

  return { context, landmarks, stoops };
}
