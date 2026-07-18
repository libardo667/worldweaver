// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Route, useLocation, useRoute } from "wouter";
import { getEntry, getShardExperience, queryMap } from "./api/ww";
import type { EntryInfo, MapEdge, MapNode, ShardExperience } from "./api/types";
import { ThemeToggle } from "./components/ThemeToggle";
import { WorldMap, type MapBounds } from "./components/WorldMap";
import { useGrounding } from "./hooks/useGrounding";
import { usePoll } from "./hooks/usePoll";
import { findNodeBySlug, isVisitablePlace, slugifyPlace } from "./lib/places";

function entryFrame(entry: EntryInfo | null): MapBounds | null {
  const coords = (entry?.entry_nodes ?? []).filter((n) => n.lat != null && n.lon != null);
  if (coords.length === 0) return null;
  const lats = coords.map((n) => n.lat as number);
  const lons = coords.map((n) => n.lon as number);
  return {
    north: Math.max(...lats),
    south: Math.min(...lats),
    east: Math.max(...lons),
    west: Math.min(...lons),
  };
}

export function App() {
  const [experience, setExperience] = useState<ShardExperience | null>(null);
  const [entry, setEntry] = useState<EntryInfo | null>(null);
  const [nodes, setNodes] = useState<MapNode[]>([]);
  const [edges, setEdges] = useState<MapEdge[]>([]);
  const viewportRef = useRef<MapBounds | null>(null);
  const atmosphere = useGrounding();
  const [, navigate] = useLocation();
  const [, placeParams] = useRoute("/place/:slug");

  useEffect(() => {
    getShardExperience().then(setExperience).catch(() => setExperience(null));
    getEntry().then(setEntry).catch(() => setEntry(null));
  }, []);

  const refreshMap = useCallback(async () => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    try {
      const result = await queryMap(viewport);
      setNodes(result.nodes);
      setEdges(result.edges);
    } catch {
      // Keep the last honest view on a failed refresh.
    }
  }, []);

  const handleViewportChange = useCallback(
    (bounds: MapBounds) => {
      viewportRef.current = bounds;
      void refreshMap();
    },
    [refreshMap],
  );

  usePoll(refreshMap, 30_000);

  const focusNode = useMemo(
    () => (placeParams?.slug ? findNodeBySlug(nodes, placeParams.slug) : undefined),
    [nodes, placeParams?.slug],
  );

  const handleNodeClick = useCallback(
    (node: MapNode) => {
      if (!isVisitablePlace(node)) return;
      navigate(`/place/${slugifyPlace(node.name)}`);
    },
    [navigate],
  );

  return (
    <div className="app-shell" data-phase={atmosphere.phase} data-haze={atmosphere.hazy ? "true" : "false"}>
      <WorldMap
        nodes={nodes}
        edges={edges}
        focusKey={focusNode?.key ?? null}
        onNodeClick={handleNodeClick}
        onViewportChange={handleViewportChange}
        frame={entryFrame(entry)}
      />
      <div className="sky-tint" aria-hidden="true" />

      <Route path="/">
        <div className="dev-caption">
          <strong>{experience?.entry_disclosure?.title ?? "WorldWeaver"}</strong>
          <span>{atmosphere.grounding?.datetime_str} — {atmosphere.grounding?.weather_description}</span>
        </div>
      </Route>
      <Route path="/place/:slug">
        {(params) => <div className="dev-caption">at: {findNodeBySlug(nodes, params.slug)?.name ?? params.slug}</div>}
      </Route>

      <ThemeToggle />
    </div>
  );
}
